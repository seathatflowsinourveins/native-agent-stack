"""Pure planning rules for the live news-LLM paper runner (no I/O, no clock reads).

Every rule the historical study preregisters (windows, guards, novelty, lanes, labels)
is taken from ``news_signal.py`` by path; this module adds only the live execution
layer: session labels, the daily schedule, basket construction, hard risk caps,
client order ids, order intents and reconciliation arithmetic.
"""

import bisect
import math
import statistics
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import ROUND_DOWN, ROUND_UP, Decimal

import common

sig = common.news_signal()
NY = common.NY

# ---------------------------------------------------------------------------------------
# Hard limits (the brief's numbers; the executor re-checks every order against them)
# ---------------------------------------------------------------------------------------

ORDER_PREFIX = "nf1-"
NOTIONAL_PER_NAME = Decimal("2000")
MAX_NAMES_PER_LEG = 12
MAX_GROSS = Decimal("40000")
MAX_ORDER_NOTIONAL = Decimal("3000")
MAX_LEVERAGE = Decimal("1")
KILL_LOSS_FRACTION = Decimal("0.015")
MAX_SPREAD_BPS = Decimal("50")
LONG_LIMIT_MULT = Decimal("1.002")
SHORT_LIMIT_MULT = Decimal("0.998")
EXT_FLATTEN_OFFSET = Decimal("0.005")
RTH_ENTRY_GRACE = timedelta(minutes=sig.RTH_ENTRY_SEARCH_MINUTES)
SSR_TRIGGER = Decimal("0.90")

# Session labels (what the user sees per stock group and timespan)
OPEN_AUCTION = "open_auction"  # after-hours/overnight headline -> 09:30 OPG entry, CLS exit
RTH = "rth"                    # 09:30-15:30 headline -> release+15 min limit entry, CLS exit
EXT_PRE = "ext_pre"            # 04:00-09:30 headline: extended-hours shadow quotes only
EXT_POST = "ext_post"          # 16:00-20:00 headline: extended-hours shadow quotes only
CLOSED = "closed"              # 20:00-04:00 or non-session day: no extended-hours segment

SESSION_CODE = {OPEN_AUCTION: "opg", RTH: "rth"}
LEG_LONG, LEG_SHORT = "long", "short"


def dec(value):
    return value if isinstance(value, Decimal) else Decimal(str(value))


def ceil_cent(price):
    price = dec(price)
    return price.quantize(Decimal("0.01") if price >= 1 else Decimal("0.0001"), rounding=ROUND_UP)


def floor_cent(price):
    price = dec(price)
    return price.quantize(Decimal("0.01") if price >= 1 else Decimal("0.0001"), rounding=ROUND_DOWN)


# ---------------------------------------------------------------------------------------
# Session calendar: labels and the daily schedule (DST and holidays via the XNYS calendar)
# ---------------------------------------------------------------------------------------


def local_at(session_date, hour, minute=0):
    return datetime(session_date.year, session_date.month, session_date.day, hour, minute, tzinfo=NY).astimezone(common.UTC)


@dataclass(frozen=True)
class DaySchedule:
    session: date
    open_utc: datetime
    close_utc: datetime
    early_close: bool
    premarket_start: datetime  # 04:00 ET
    basket_at: datetime        # open - 15 min (09:15)
    opg_submit_by: datetime    # open - 3 min (09:27), our cutoff
    opg_broker_cutoff: datetime  # open - 2 min (09:28), Alpaca's OPG cutoff
    cls_start: datetime        # close - 20 min (15:40)
    cls_end: datetime          # close - 15 min (15:45)
    market_flatten_at: datetime  # close - 5 min (15:55)
    ext_flatten_at: datetime   # close + 2 min
    ext_end: datetime          # 20:00 ET (17:00 on early-close days)
    service_end: datetime      # ext_end + 5 min


def day_schedule(calendar, session_date):
    s = calendar.get(session_date)
    ext_end = s.close_utc + timedelta(hours=4)
    return DaySchedule(
        session=s.session,
        open_utc=s.open_utc,
        close_utc=s.close_utc,
        early_close=s.early_close,
        premarket_start=local_at(s.session, 4),
        basket_at=s.open_utc - timedelta(minutes=15),
        opg_submit_by=s.open_utc - timedelta(minutes=3),
        opg_broker_cutoff=s.open_utc - timedelta(minutes=2),
        cls_start=s.close_utc - timedelta(minutes=20),
        cls_end=s.close_utc - timedelta(minutes=15),
        market_flatten_at=s.close_utc - timedelta(minutes=5),
        ext_flatten_at=s.close_utc + timedelta(minutes=2),
        ext_end=ext_end,
        service_end=ext_end + timedelta(minutes=5),
    )


def is_session(calendar, day):
    try:
        calendar.index_of(day)
        return True
    except KeyError:
        return False


def extended_segment(calendar, t_utc):
    """EXT_PRE for 04:00 to the open, EXT_POST for the close to 20:00 (or close+4h), else CLOSED."""
    t = sig.as_utc(t_utc)
    day = t.astimezone(NY).date()
    if not is_session(calendar, day):
        return CLOSED
    s = calendar.get(day)
    if local_at(day, 4) <= t < s.open_utc:
        return EXT_PRE
    if s.close_utc <= t < s.close_utc + timedelta(hours=4):
        return EXT_POST
    return CLOSED


def session_label(window):
    """Trading label of a study window: open_auction, rth, or the study's exclusion kind."""
    if window.kind == sig.OVERNIGHT:
        return OPEN_AUCTION
    if window.kind == sig.RTH:
        return RTH
    return window.kind


def opg_submission_allowed(schedule, now):
    return schedule.basket_at <= now <= schedule.opg_submit_by


def cls_submission_allowed(schedule, now):
    return schedule.cls_start <= now <= schedule.cls_end


# ---------------------------------------------------------------------------------------
# Article screening: the study's guards in the study's order (prepare.scan_news)
# ---------------------------------------------------------------------------------------


class Screener:
    """Stateful but I/O-free: the 24-hour novelty tracker and the id-order index.

    Feed every received article (any symbol count) in (created_at, id) order. Returns a
    candidate dict for a single-symbol Benzinga article that passes the relevance
    (primary operating company), timestamp, D5 movement, novelty and id-order guards,
    else a drop reason.
    """

    def __init__(self, calendar, assets):
        self.calendar = calendar
        self.assets = assets  # symbol -> asset dict (symbol, name, exchange, status, ...)
        self.tracker = sig.DuplicateTracker()
        self._ids = []    # sorted numeric news ids
        self._times = {}  # id -> created_at epoch seconds
        self._last_prune_day = None

    def _id_order_suspect(self, nid, created):
        if nid is None:
            return False
        pos = bisect.bisect_left(self._ids, nid)
        preds = [self._times[i] for i in self._ids[max(0, pos - sig.ID_ORDER_PREDECESSORS):pos]]
        lag = sig.id_order_lag(preds, int(created.timestamp()))
        return lag is not None and lag > sig.ID_ORDER_GUARD_SECONDS

    def screen(self, article):
        try:
            created = sig.as_utc(article["created_at"])
        except (KeyError, ValueError, TypeError):
            return None, "drop_bad_created_at"
        raw_id = str(article.get("id", ""))
        nid = int(raw_id) if raw_id.isdigit() else None
        if nid is not None and nid not in self._times:
            bisect.insort(self._ids, nid)
            self._times[nid] = int(created.timestamp())
        symbols = sig.parse_symbols(article.get("symbols"))
        norm = sig.normalize_headline(article.get("headline"))
        if symbols is None:
            return None, "drop_unparseable_symbols"
        duplicate = len(symbols) == 1 and self.tracker.seen_recently(symbols[0], created, norm)
        self.tracker.record(symbols, created, norm)
        day = created.date()
        if day != self._last_prune_day:
            self.tracker.prune_all(created)
            self._last_prune_day = day
        if len(symbols) != 1:
            return None, "drop_symbol_count_not_1" if symbols else "drop_no_symbols"
        if str(article.get("source", "")).lower() != "benzinga":
            return None, "drop_source_not_benzinga"
        symbol = symbols[0]
        asset = self.assets.get(symbol)
        if asset is None:
            return None, "drop_symbol_not_in_asset_master"
        if not sig.is_primary_operating_company(symbol, asset.get("name"), asset.get("exchange")):
            return None, "drop_not_primary_operating_company"
        window = self.calendar.classify(created)
        if window.kind not in (sig.OVERNIGHT, sig.RTH):
            return None, f"drop_window_{window.kind}"
        updated = None
        if article.get("updated_at"):
            try:
                updated = sig.as_utc(article["updated_at"])
            except ValueError:
                updated = None
        ok, reason = sig.timestamp_guard(window, updated)
        if not ok:
            return None, f"drop_guard_{reason}"
        headline = sig.clean_headline(article.get("headline"))
        if not headline:
            return None, "drop_empty_headline"
        if sig.is_movement_headline(headline):
            return None, "drop_movement_headline"
        if duplicate:
            return None, "drop_duplicate_24h"
        try:
            ckpt = sig.checkpoint_year(created)
        except ValueError:
            return None, "drop_headline_year_before_2016"
        if self._id_order_suspect(nid, created):
            return None, "drop_guard_id_order"
        return {
            "news_id": raw_id,
            "event_id": f"{raw_id}:{symbol}",
            "symbol": symbol,
            "company": sig.clean_company_name(asset.get("name")),
            "exchange": asset.get("exchange"),
            "headline": headline,
            "created_at": common.iso(created),
            "updated_at": common.iso(updated),
            "window": window.kind,
            "sub": window.sub,
            "session": window.session.isoformat(),
            "session_label": session_label(window),
            "entry_utc": common.iso(window.entry_utc),
            "exit_utc": common.iso(window.exit_utc),
            "checkpoint_year": ckpt,
            "variant": sig.OPERATIVE_VARIANT,
        }, "ok"


# ---------------------------------------------------------------------------------------
# Liquidity lanes and Rule 201 from pre-decision daily bars
# ---------------------------------------------------------------------------------------


def bars_by_session(bars):
    """Alpaca daily bars (t at New York midnight, raw adjustment) -> {date: bar}."""
    out = {}
    for bar in bars or []:
        day = sig.as_utc(bar["t"]).astimezone(NY).date()
        out[day] = bar
    return out


def lane_from_bars(calendar, trade_session, bars):
    """(lane, prior_close, median_dollar_volume_20, complete) from sessions before trade_session."""
    by_day = bars_by_session(bars)
    prior = calendar.prior_sessions(trade_session, sig.LOOKBACK_SESSIONS)
    if not prior:
        return None, None, None, False
    complete = all(d in by_day for d in prior)
    last = by_day.get(prior[-1])
    prior_close = float(last["c"]) if last else None
    dvs = [float(by_day[d]["c"]) * float(by_day[d]["v"]) for d in prior if d in by_day]
    med = statistics.median(dvs) if dvs else None
    return sig.lane_for(prior_close, med, complete), prior_close, med, complete


def ssr_active(calendar, trade_session, bars, today_low=None):
    """Rule 201 short-sale restriction in force on trade_session, from pre-decision data.

    True when the previous session's low was at least 10% below the close before it
    (carry-over to the next day), or when today's low so far is at least 10% below the
    previous close. Missing data is treated as restricted (fail-closed: no short).
    """
    by_day = bars_by_session(bars)
    prev = calendar.prior_sessions(trade_session, 2)
    if not prev:
        return True
    d2, d1 = prev
    if d1 not in by_day or d2 not in by_day:
        return True
    prev_close = dec(by_day[d1]["c"])
    if dec(by_day[d1]["l"]) <= SSR_TRIGGER * dec(by_day[d2]["c"]):
        return True
    if today_low is not None and dec(today_low) <= SSR_TRIGGER * prev_close:
        return True
    return False


def short_allowed(asset, ssr):
    if not asset or not asset.get("shortable"):
        return False, "not_shortable"
    if not asset.get("easy_to_borrow"):
        return False, "not_easy_to_borrow"
    if ssr:
        return False, "ssr_rule_201"
    return True, "ok"


def side_for_label(label):
    return {"FAVORABLE": LEG_LONG, "UNFAVORABLE": LEG_SHORT}.get(label)


# ---------------------------------------------------------------------------------------
# Client order ids and intents
# ---------------------------------------------------------------------------------------


def client_order_id(session_date, session_code, symbol, leg):
    """nf1-<yyyymmdd>-<session>-<symbol>-<leg>: one id per intent, so resubmission is idempotent."""
    return f"{ORDER_PREFIX}{session_date.strftime('%Y%m%d')}-{session_code}-{symbol}-{leg}"


def is_nf1(client_id):
    return isinstance(client_id, str) and client_id.startswith(ORDER_PREFIX)


def whole_qty(notional, price):
    price = dec(price)
    if price <= 0:
        return 0
    return int((dec(notional) / price).to_integral_value(rounding=ROUND_DOWN))


def entry_intent(session_date, label_code, symbol, leg, qty, tif, limit_price=None):
    intent = {
        "symbol": symbol,
        "qty": str(qty),
        "side": "buy" if leg == LEG_LONG else "sell",
        "type": "market" if limit_price is None else "limit",
        "time_in_force": tif,
        "client_order_id": client_order_id(session_date, label_code, symbol, leg),
    }
    if limit_price is not None:
        intent["limit_price"] = format(dec(limit_price), "f")
    return intent


def exit_intent(session_date, stage, symbol, position_qty, limit_price=None, extended=False):
    """Close a position: stage is cls, mkt, ext or kill; the leg is the side being closed."""
    qty = dec(position_qty)
    leg = LEG_LONG if qty > 0 else LEG_SHORT
    tif = "cls" if stage == "cls" else "day"
    intent = {
        "symbol": symbol,
        "qty": format(abs(qty).normalize(), "f"),
        "side": "sell" if leg == LEG_LONG else "buy",
        "type": "market" if limit_price is None else "limit",
        "time_in_force": tif,
        "client_order_id": client_order_id(session_date, stage, symbol, leg),
    }
    if limit_price is not None:
        intent["limit_price"] = format(dec(limit_price), "f")
    if extended:
        intent["extended_hours"] = True
    return intent


AUCTION_TIFS = ("opg", "cls")


def contract_envelope(intent):
    """Validate an intent with order_contract.build_envelope before any submission.

    order_contract v1 admits only time_in_force "day". Auction orders (opg/cls) are
    validated on every other field with the contract itself, then admitted by this
    documented local extension only as simple market orders without extended hours.
    """
    oc = common.order_contract()
    tif = intent.get("time_in_force")
    extended = intent.get("extended_hours") is True
    if tif in AUCTION_TIFS:
        if intent.get("type") != "market" or extended or "limit_price" in intent:
            raise oc.ContractError("time_in_force: auction orders must be plain market orders")
        envelope = oc.build_envelope({**intent, "time_in_force": "day"})
        envelope["intent"]["time_in_force"] = tif
        envelope["local_extension"] = {
            "time_in_force": tif,
            "reason": "order_contract v1 admits only day; news-forward admits opg/cls for simple market auction orders",
        }
        return envelope
    if extended and intent.get("type") != "limit":
        raise oc.ContractError("extended_hours: limit orders only")
    return oc.build_envelope(intent, extended_hours_allowed=extended)


# ---------------------------------------------------------------------------------------
# Hard caps
# ---------------------------------------------------------------------------------------


@dataclass
class Exposure:
    gross: Decimal = Decimal("0")
    names: dict = field(default_factory=dict)  # (window_label, leg) -> count
    symbols: set = field(default_factory=set)  # symbols held or pending today


def entry_cap_violation(notional, window_label, leg, symbol, exposure, equity):
    """None when an entry fits every hard cap, else the violated cap's name."""
    notional = dec(notional)
    if notional <= 0:
        return "zero_notional"
    if notional > MAX_ORDER_NOTIONAL:
        return "per_order_notional_cap"
    if notional > NOTIONAL_PER_NAME * Decimal("1.0001"):
        return "per_name_notional_cap"
    if symbol in exposure.symbols:
        return "symbol_already_traded_today"
    if exposure.names.get((window_label, leg), 0) >= MAX_NAMES_PER_LEG:
        return "names_per_leg_cap"
    if exposure.gross + notional > MAX_GROSS:
        return "gross_exposure_cap"
    if equity is not None and exposure.gross + notional > dec(equity) * MAX_LEVERAGE:
        return "leverage_cap"
    return None


def commit_entry(exposure, notional, window_label, leg, symbol):
    exposure.gross += dec(notional)
    key = (window_label, leg)
    exposure.names[key] = exposure.names.get(key, 0) + 1
    exposure.symbols.add(symbol)


def kill_switch_triggered(start_equity, equity):
    if start_equity is None or equity is None:
        return False
    return dec(equity) <= dec(start_equity) * (1 - KILL_LOSS_FRACTION)


# ---------------------------------------------------------------------------------------
# The 09:15 open-auction basket
# ---------------------------------------------------------------------------------------


def build_open_basket(events, session_date, exposure, equity):
    """Decisions and OPG intents for scored overnight events of one session.

    events: dicts with symbol, created_at, news_id, lane, label, ref_price, asset, ssr.
    Only the liquid lane trades; FAVORABLE goes long; UNFAVORABLE goes short only when
    shortable, easy to borrow and not under Rule 201. Each leg takes its first 12 names
    by (created_at, news_id); a leg needs >= 2 names (the study's portfolio rule); gross
    exposure is filled in release order across both legs until the cap.
    """
    decisions, legs = [], {LEG_LONG: [], LEG_SHORT: []}
    ordered = sorted(events, key=lambda e: (e["created_at"], int(e["news_id"]) if str(e["news_id"]).isdigit() else 0))
    seen = set()
    for ev in ordered:
        base = {"event_id": ev.get("event_id"), "symbol": ev["symbol"], "session_label": OPEN_AUCTION,
                "lane": ev.get("lane"), "label": ev.get("label")}
        if ev["symbol"] in seen:
            decisions.append({**base, "action": "skip", "reason": "not_first_in_window"})
            continue
        seen.add(ev["symbol"])
        if ev.get("lane") != sig.LIQUID:
            decisions.append({**base, "action": "shadow", "reason": f"lane_{ev.get('lane')}_shadow_only"})
            continue
        leg = side_for_label(ev.get("label"))
        if leg is None:
            decisions.append({**base, "action": "skip", "reason": f"label_{str(ev.get('label')).lower()}"})
            continue
        if leg == LEG_SHORT:
            ok, why = short_allowed(ev.get("asset"), ev.get("ssr", True))
            if not ok:
                decisions.append({**base, "leg": leg, "action": "skip", "reason": why})
                continue
        if not ev.get("asset", {}).get("tradable", False):
            decisions.append({**base, "leg": leg, "action": "skip", "reason": "not_tradable"})
            continue
        price = ev.get("ref_price")
        if not price or dec(price) <= 0:
            decisions.append({**base, "leg": leg, "action": "skip", "reason": "no_reference_price"})
            continue
        if len(legs[leg]) >= MAX_NAMES_PER_LEG:
            decisions.append({**base, "leg": leg, "action": "skip", "reason": "names_per_leg_cap"})
            continue
        legs[leg].append((ev, base))
    intents = []
    chosen = {LEG_LONG: [], LEG_SHORT: []}
    queue = sorted([(ev["created_at"], leg, ev, base) for leg in legs for ev, base in legs[leg]], key=lambda x: x[0])
    trial = Exposure(exposure.gross, dict(exposure.names), set(exposure.symbols))
    for _, leg, ev, base in queue:
        qty = whole_qty(NOTIONAL_PER_NAME, ev["ref_price"])
        notional = dec(qty) * dec(ev["ref_price"])
        if qty < 1:
            decisions.append({**base, "leg": leg, "action": "skip", "reason": "price_above_name_notional"})
            continue
        why = entry_cap_violation(notional, OPEN_AUCTION, leg, ev["symbol"], trial, equity)
        if why:
            decisions.append({**base, "leg": leg, "action": "skip", "reason": why})
            continue
        commit_entry(trial, notional, OPEN_AUCTION, leg, ev["symbol"])
        chosen[leg].append((ev, base, qty, notional))
    for leg, rows in chosen.items():
        if 0 < len(rows) < sig.MIN_NAMES_PER_LEG:
            for ev, base, qty, notional in rows:
                decisions.append({**base, "leg": leg, "action": "skip", "reason": "leg_below_min_names"})
            continue
        for ev, base, qty, notional in rows:
            intent = entry_intent(session_date, SESSION_CODE[OPEN_AUCTION], ev["symbol"], leg, qty, "opg")
            decisions.append({**base, "leg": leg, "action": "enter", "reason": "ok", "qty": qty,
                              "ref_price": str(ev["ref_price"]), "est_notional": str(notional),
                              "client_order_id": intent["client_order_id"]})
            intents.append(intent)
            commit_entry(exposure, notional, OPEN_AUCTION, leg, ev["symbol"])
    return decisions, intents


# ---------------------------------------------------------------------------------------
# Regular-session entries (release + 15 min, marketable limit on the latest SIP quote)
# ---------------------------------------------------------------------------------------


def spread_bps(bid, ask):
    bid, ask = dec(bid), dec(ask)
    if bid <= 0 or ask <= 0 or ask < bid:
        return None
    return (ask - bid) / ((ask + bid) / 2) * Decimal("10000")


def plan_rth_entry(ev, quote, now, session_date, exposure, equity):
    """(decision, intent|None) for one scored RTH event at its entry time."""
    base = {"event_id": ev.get("event_id"), "symbol": ev["symbol"], "session_label": RTH,
            "lane": ev.get("lane"), "label": ev.get("label")}
    if ev.get("lane") != sig.LIQUID:
        return {**base, "action": "shadow", "reason": f"lane_{ev.get('lane')}_shadow_only"}, None
    leg = side_for_label(ev.get("label"))
    if leg is None:
        return {**base, "action": "skip", "reason": f"label_{str(ev.get('label')).lower()}"}, None
    base["leg"] = leg
    entry = sig.as_utc(ev["entry_utc"])
    if now < entry:
        return {**base, "action": "wait", "reason": "before_entry_time"}, None
    if now - entry > RTH_ENTRY_GRACE:
        return {**base, "action": "skip", "reason": "entry_late"}, None
    if leg == LEG_SHORT:
        ok, why = short_allowed(ev.get("asset"), ev.get("ssr", True))
        if not ok:
            return {**base, "action": "skip", "reason": why}, None
    if not ev.get("asset", {}).get("tradable", False):
        return {**base, "action": "skip", "reason": "not_tradable"}, None
    if not quote or not quote.get("bp") or not quote.get("ap"):
        return {**base, "action": "skip", "reason": "no_two_sided_quote"}, None
    bps = spread_bps(quote["bp"], quote["ap"])
    if bps is None:
        return {**base, "action": "skip", "reason": "crossed_or_invalid_quote"}, None
    if bps > MAX_SPREAD_BPS:
        return {**base, "action": "skip", "reason": "spread_above_50bps", "spread_bps": str(bps.quantize(Decimal('0.1')))}, None
    limit = ceil_cent(dec(quote["ap"]) * LONG_LIMIT_MULT) if leg == LEG_LONG else floor_cent(dec(quote["bp"]) * SHORT_LIMIT_MULT)
    qty = whole_qty(NOTIONAL_PER_NAME, limit)
    if qty < 1:
        return {**base, "action": "skip", "reason": "price_above_name_notional"}, None
    notional = dec(qty) * limit
    why = entry_cap_violation(notional, RTH, leg, ev["symbol"], exposure, equity)
    if why:
        return {**base, "action": "skip", "reason": why}, None
    intent = entry_intent(session_date, SESSION_CODE[RTH], ev["symbol"], leg, qty, "day", limit)
    commit_entry(exposure, notional, RTH, leg, ev["symbol"])
    return {**base, "action": "enter", "reason": "ok", "qty": qty, "limit_price": str(limit),
            "spread_bps": str(bps.quantize(Decimal("0.1"))), "est_notional": str(notional),
            "client_order_id": intent["client_order_id"]}, intent


# ---------------------------------------------------------------------------------------
# Close-out
# ---------------------------------------------------------------------------------------


def plan_cls_exits(positions, session_date, covered):
    """CLS market exits for nf1 positions (15:40-15:45) not already covered by an exit order."""
    return [exit_intent(session_date, "cls", p["symbol"], p["qty"]) for p in positions
            if dec(p["qty"]) != 0 and p["symbol"] not in covered]


def plan_market_flatten(positions, session_date, covered):
    """15:55: a day market order for any position still open and not covered by a live exit."""
    return [exit_intent(session_date, "mkt", p["symbol"], p["qty"]) for p in positions
            if dec(p["qty"]) != 0 and p["symbol"] not in covered]


def plan_ext_flatten(positions, quotes, session_date, stage="ext"):
    """After the close: extended-hours limit exits at bid -0.5% (sell) or ask +0.5% (buy)."""
    out, missing = [], []
    for p in positions:
        qty = dec(p["qty"])
        if qty == 0:
            continue
        q = quotes.get(p["symbol"]) or {}
        if qty > 0 and q.get("bp"):
            price = floor_cent(dec(q["bp"]) * (1 - EXT_FLATTEN_OFFSET))
        elif qty < 0 and q.get("ap"):
            price = ceil_cent(dec(q["ap"]) * (1 + EXT_FLATTEN_OFFSET))
        else:
            missing.append(p["symbol"])
            continue
        out.append(exit_intent(session_date, stage, p["symbol"], qty, limit_price=price, extended=True))
    return out, missing


# ---------------------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------------------


def realized_pnl(fills):
    """Sum of signed cash flows of filled nf1 orders (sells +, buys -)."""
    total = Decimal("0")
    sold = Decimal("0")
    for f in fills:
        notional = dec(f["filled_qty"]) * dec(f["filled_avg_price"])
        if f["side"] == "sell":
            total += notional
            sold += notional
        else:
            total -= notional
    return total, sold


def reconcile(start_cash, end_cash, fills, positions, open_orders):
    """End-of-day check: flat, no open nf1 orders, cash change equals realized P&L within fees.

    Fee tolerance: SEC Section 31 at up to $30.90 per million sold plus FINRA TAF at up
    to $0.000195/share (capped $9.79/trade), bounded here by 0.1% of sold notional + $1.
    """
    pnl, sold = realized_pnl(fills)
    cash_change = dec(end_cash) - dec(start_cash)
    tolerance = sold * Decimal("0.001") + Decimal("1")
    diff = cash_change - pnl
    problems = []
    nf1_positions = [p for p in positions if dec(p["qty"]) != 0]
    if nf1_positions:
        problems.append("positions_open")
    if [o for o in open_orders if is_nf1(o.get("client_order_id"))]:
        problems.append("orders_open")
    if abs(diff) > tolerance:
        problems.append("cash_mismatch")
    return {
        "ok": not problems,
        "problems": problems,
        "realized_pnl": str(pnl),
        "cash_change": str(cash_change),
        "difference": str(diff),
        "tolerance": str(tolerance),
        "fills": len(fills),
        "open_positions": [p["symbol"] for p in nf1_positions],
    }


def shadow_times(release_utc, received_utc):
    """Quote snapshots at release (or receipt if later), +15 and +60 minutes."""
    release = sig.as_utc(release_utc)
    first = max(release, sig.as_utc(received_utc))
    return [("release", first), ("plus15", release + timedelta(minutes=15)), ("plus60", release + timedelta(minutes=60))]


def finite(x):
    return x is not None and not (isinstance(x, float) and (math.isnan(x) or math.isinf(x)))
