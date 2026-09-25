"""Pure planning rules for the live news-LLM paper runner (no I/O, no clock reads).

Every rule the historical study preregisters (windows, guards, novelty, lanes, labels)
is taken from ``news_signal.py`` by path; this module adds only the live execution
layer: session labels, the daily schedule, risk-scaled sizing, basket construction,
hard risk caps, per-arm client order ids and ledgers, order intents and
reconciliation arithmetic.

Arms (each with its own client-id prefix and gross cap):
  core  nf1-       confirmatory path: open auction / RTH entry, CLS exit, flat by the close
  pm    nf1x-pm-   exploratory: 04:00-09:00 liquid headlines, extended-hours entry at
                   release + 15 min, CLS exit
  ah    nf1x-ah-   exploratory: 16:00-19:30 headlines, extended-hours entry at release
                   + 15 min, held overnight, exit at the next session's OPG
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

CORE, PM, AH = "core", "pm", "ah"
ARM_PREFIX = {CORE: "nf1-", PM: "nf1x-pm-", AH: "nf1x-ah-"}
ARM_LABEL = {CORE: "confirmatory_pilot", PM: "exploratory", AH: "exploratory"}
ORDER_PREFIX = ARM_PREFIX[CORE]
MAX_NAMES_PER_LEG = 12
# Section A sizing: notional_i = min(0.0015 E / sigma_i, 0.5% MDV20_i, 5% E)
RISK_BUDGET = Decimal("0.0015")
MDV_FRACTION = Decimal("0.005")
MAX_NAME_FRACTION = Decimal("0.05")
MIN_NAME_NOTIONAL = Decimal("1000")
ARM_SIZE_FRACTION = Decimal("0.25")   # exploratory arms trade 25% of the section-A size
ARM_GROSS_FRACTION = Decimal("0.25")  # and each has its own gross cap of 0.25 E
KILL_LOSS_FRACTION = Decimal("0.02")
MAX_SPREAD_BPS = Decimal("50")
EXT_MAX_SPREAD_BPS = Decimal("100")
LONG_LIMIT_MULT = Decimal("1.002")
SHORT_LIMIT_MULT = Decimal("0.998")
EXT_LONG_LIMIT_MULT = Decimal("1.003")
EXT_SHORT_LIMIT_MULT = Decimal("0.997")
EXT_FLATTEN_OFFSET = Decimal("0.005")
AH_LAST_RELEASE = (19, 30)  # D2 takes headlines released 16:00-19:30 ET
PM_LAST_RELEASE = (9, 0)    # D1 takes headlines released 04:00-09:00 ET
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


def sigma_from_bars(calendar, trade_session, bars):
    """Sample stdev of the 20 daily close-to-close returns before trade_session (21 closes), else None."""
    by_day = bars_by_session(bars)
    prior = calendar.prior_sessions(trade_session, sig.LOOKBACK_SESSIONS + 1)
    if not prior or not all(d in by_day for d in prior):
        return None
    closes = [float(by_day[d]["c"]) for d in prior]
    if min(closes) <= 0:
        return None
    rets = [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes))]
    return statistics.stdev(rets)


def risk_notional(equity, sigma, mdv20, fraction=Decimal("1")):
    """Section A: min(0.0015 E / sigma, 0.5% MDV20, 5% E), times the arm fraction; None if unknown."""
    if equity is None or sigma is None or mdv20 is None or sigma <= 0:
        return None
    e = dec(equity)
    size = min(RISK_BUDGET * e / dec(sigma), MDV_FRACTION * dec(mdv20), MAX_NAME_FRACTION * e)
    return (size * dec(fraction)).quantize(Decimal("0.01"), rounding=ROUND_DOWN)


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
# Client order ids, parsing and per-arm ledgers
# ---------------------------------------------------------------------------------------


def client_order_id(session_date, stage, symbol, leg, arm=CORE):
    """<prefix><yyyymmdd>-<stage>-<symbol>-<leg>; one id per intent, so resubmission is idempotent.

    core: nf1-20260925-opg-ACME-long; arms: nf1x-pm-20260925-ent-ACME-long. The date is the
    entry session's date for every leg of a position, including an overnight exit.
    """
    return f"{ARM_PREFIX[arm]}{session_date.strftime('%Y%m%d')}-{stage}-{symbol}-{leg}"


def is_nf1(client_id):
    """True for every id this runner issues (nf1- core, nf1x-pm- and nf1x-ah- arms)."""
    return isinstance(client_id, str) and any(client_id.startswith(p) for p in ARM_PREFIX.values())


def parse_cid(client_id):
    """{arm, date, stage, symbol, leg} for one of our ids, else None."""
    if not is_nf1(client_id):
        return None
    for arm, prefix in ARM_PREFIX.items():
        if client_id.startswith(prefix):
            parts = client_id[len(prefix):].split("-")
            if len(parts) != 4 or len(parts[0]) != 8 or not parts[0].isdigit():
                return None
            day = date(int(parts[0][:4]), int(parts[0][4:6]), int(parts[0][6:]))
            return {"arm": arm, "date": day, "stage": parts[1], "symbol": parts[2], "leg": parts[3]}
    return None


ENTRY_STAGES = ("opg", "rth", "ent")


def ledger(orders):
    """{(arm, entry_date, symbol): signed filled qty} from our orders (buys +, sells -)."""
    out = {}
    for o in orders:
        info = parse_cid(o.get("client_order_id"))
        qty = dec(o.get("filled_qty") or 0)
        if info is None or qty == 0:
            continue
        key = (info["arm"], info["date"], info["symbol"])
        out[key] = out.get(key, Decimal("0")) + (qty if o.get("side") == "buy" else -qty)
    return {k: v for k, v in out.items() if v != 0}


def whole_qty(notional, price):
    price = dec(price)
    if price <= 0:
        return 0
    return int((dec(notional) / price).to_integral_value(rounding=ROUND_DOWN))


def entry_intent(session_date, stage, symbol, leg, qty, tif, limit_price=None, arm=CORE, extended=False):
    intent = {
        "symbol": symbol,
        "qty": str(qty),
        "side": "buy" if leg == LEG_LONG else "sell",
        "type": "market" if limit_price is None else "limit",
        "time_in_force": tif,
        "client_order_id": client_order_id(session_date, stage, symbol, leg, arm),
    }
    if limit_price is not None:
        intent["limit_price"] = format(dec(limit_price), "f")
    if extended:
        intent["extended_hours"] = True
    return intent


def exit_intent(entry_date, stage, symbol, position_qty, limit_price=None, extended=False, arm=CORE, tif=None):
    """Close an arm's holding: stage cls, mkt, ext<n>, kill or opg; the leg is the side being closed."""
    qty = dec(position_qty)
    leg = LEG_LONG if qty > 0 else LEG_SHORT
    tif = tif or ("cls" if stage == "cls" else "opg" if stage == "opg" else "day")
    intent = {
        "symbol": symbol,
        "qty": format(abs(qty).normalize(), "f"),
        "side": "sell" if leg == LEG_LONG else "buy",
        "type": "market" if limit_price is None else "limit",
        "time_in_force": tif,
        "client_order_id": client_order_id(entry_date, stage, symbol, leg, arm),
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
    Extended-hours orders must be day limit orders (the contract's
    ``extended_hours_allowed`` widening).
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
# Hard caps (per arm) and the kill switch
# ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Limits:
    """Per-arm caps: gross = L x E (core) or 0.25 E (each arm); per order = 5% E."""
    equity: Decimal
    gross_cap: Decimal
    per_order_cap: Decimal

    @classmethod
    def for_arm(cls, arm, equity, leverage, extra_cap=None):
        e = dec(equity)
        gross = dec(leverage) * e if arm == CORE else ARM_GROSS_FRACTION * e
        if extra_cap is not None:
            gross = min(gross, dec(extra_cap))
        return cls(e, gross, MAX_NAME_FRACTION * e)


@dataclass
class Exposure:
    gross: Decimal = Decimal("0")
    names: dict = field(default_factory=dict)  # (window_label, leg) -> count
    symbols: set = field(default_factory=set)  # symbols this arm holds or has pending today


def entry_cap_violation(notional, window_label, leg, symbol, exposure, limits, account=None):
    """None when an entry fits every hard cap, else the violated cap's name.

    account: optional (total gross of all arms, account gross cap) for the cross-arm check.
    """
    notional = dec(notional)
    if notional <= 0:
        return "zero_notional"
    if notional > limits.per_order_cap:
        return "per_order_notional_cap"
    if symbol in exposure.symbols:
        return "symbol_already_traded_today"
    if exposure.names.get((window_label, leg), 0) >= MAX_NAMES_PER_LEG:
        return "names_per_leg_cap"
    if exposure.gross + notional > limits.gross_cap:
        return "gross_exposure_cap"
    if account is not None and dec(account[0]) + notional > dec(account[1]):
        return "account_gross_cap"
    return None


def commit_entry(exposure, notional, window_label, leg, symbol):
    exposure.gross += dec(notional)
    key = (window_label, leg)
    exposure.names[key] = exposure.names.get(key, 0) + 1
    exposure.symbols.add(symbol)


def kill_switch_triggered(start_equity, equity):
    """Daily loss kill: equity at or below 98% of start-of-day equity."""
    if start_equity is None or equity is None:
        return False
    return dec(equity) <= dec(start_equity) * (1 - KILL_LOSS_FRACTION)


def sized_qty(target_notional, price):
    """(qty, notional, skip_reason) under section A's whole-share and $1,000 minimums."""
    if target_notional is None:
        return 0, Decimal("0"), "no_risk_size"
    qty = whole_qty(target_notional, price)
    notional = dec(qty) * dec(price)
    if qty < 1:
        return 0, notional, "below_one_share"
    if notional < MIN_NAME_NOTIONAL:
        return 0, notional, "below_min_notional"
    return qty, notional, None


# ---------------------------------------------------------------------------------------
# The 09:15 open-auction basket (core)
# ---------------------------------------------------------------------------------------


def build_open_basket(events, session_date, exposure, limits, account_gross=None, blocked=frozenset()):
    """Decisions and OPG intents for scored overnight events of one session.

    events: dicts with symbol, created_at, news_id, lane, label, ref_price, asset, ssr and
    target_notional (section A size). Only the liquid lane trades; FAVORABLE goes long;
    UNFAVORABLE goes short only when shortable, easy to borrow and not under Rule 201.
    Each leg takes its first 12 names by (created_at, news_id); a leg needs >= 2 names
    (the study's portfolio rule); gross is filled in release order across both legs up
    to the arm's cap. ``blocked``: symbols another arm holds (e.g. an overnight D2
    position exiting in the same auction).
    account_gross: optional [total gross of all arms, account cap], updated in place.
    """
    decisions, legs = [], {LEG_LONG: [], LEG_SHORT: []}
    ordered = sorted(events, key=lambda e: (e["created_at"], int(e["news_id"]) if str(e["news_id"]).isdigit() else 0))
    seen = set()
    for ev in ordered:
        base = {"event_id": ev.get("event_id"), "symbol": ev["symbol"], "session_label": OPEN_AUCTION,
                "lane": ev.get("lane"), "label": ev.get("label"), "arm": CORE}
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
        if ev["symbol"] in blocked:
            decisions.append({**base, "leg": leg, "action": "skip", "reason": "symbol_held_by_other_arm"})
            continue
        if leg == LEG_SHORT:
            ok, why = short_allowed(ev.get("asset"), ev.get("ssr", True))
            if not ok:
                decisions.append({**base, "leg": leg, "action": "skip", "reason": why})
                continue
        if not (ev.get("asset") or {}).get("tradable", False):
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
    chosen = {LEG_LONG: [], LEG_SHORT: []}
    queue = sorted([(ev["created_at"], leg, ev, base) for leg in legs for ev, base in legs[leg]], key=lambda x: x[0])
    trial = Exposure(exposure.gross, dict(exposure.names), set(exposure.symbols))
    trial_account = list(account_gross) if account_gross is not None else None
    for _, leg, ev, base in queue:
        qty, notional, why = sized_qty(ev.get("target_notional"), ev["ref_price"])
        if why:
            decisions.append({**base, "leg": leg, "action": "skip", "reason": why,
                              "target_notional": str(ev.get("target_notional"))})
            continue
        why = entry_cap_violation(notional, OPEN_AUCTION, leg, ev["symbol"], trial, limits, trial_account)
        if why:
            decisions.append({**base, "leg": leg, "action": "skip", "reason": why})
            continue
        commit_entry(trial, notional, OPEN_AUCTION, leg, ev["symbol"])
        if trial_account is not None:
            trial_account[0] = dec(trial_account[0]) + notional
        chosen[leg].append((ev, base, qty, notional))
    intents = []
    for leg, rows in chosen.items():
        if 0 < len(rows) < sig.MIN_NAMES_PER_LEG:
            for ev, base, qty, notional in rows:
                decisions.append({**base, "leg": leg, "action": "skip", "reason": "leg_below_min_names"})
            continue
        for ev, base, qty, notional in rows:
            intent = entry_intent(session_date, SESSION_CODE[OPEN_AUCTION], ev["symbol"], leg, qty, "opg")
            decisions.append({**base, "leg": leg, "action": "enter", "reason": "ok", "qty": qty,
                              "ref_price": str(ev["ref_price"]), "est_notional": str(notional),
                              "target_notional": str(ev.get("target_notional")), "sigma": ev.get("sigma"),
                              "client_order_id": intent["client_order_id"]})
            intents.append(intent)
            commit_entry(exposure, notional, OPEN_AUCTION, leg, ev["symbol"])
            if account_gross is not None:
                account_gross[0] = dec(account_gross[0]) + notional
    return decisions, intents


# ---------------------------------------------------------------------------------------
# Regular-session entries (release + 15 min, marketable limit on the latest SIP quote)
# ---------------------------------------------------------------------------------------


def spread_bps(bid, ask):
    bid, ask = dec(bid), dec(ask)
    if bid <= 0 or ask <= 0 or ask < bid:
        return None
    return (ask - bid) / ((ask + bid) / 2) * Decimal("10000")


def _marketable_entry(ev, quote, now, session_date, exposure, limits, *, arm, window_label, stage, max_bps,
                      long_mult, short_mult, extended, account=None):
    base = {"event_id": ev.get("event_id"), "symbol": ev["symbol"], "session_label": window_label,
            "lane": ev.get("lane"), "label": ev.get("label"), "arm": arm}
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
    if not (ev.get("asset") or {}).get("tradable", False):
        return {**base, "action": "skip", "reason": "not_tradable"}, None
    if not quote or not quote.get("bp") or not quote.get("ap"):
        return {**base, "action": "skip", "reason": "no_two_sided_quote"}, None
    bps = spread_bps(quote["bp"], quote["ap"])
    if bps is None:
        return {**base, "action": "skip", "reason": "crossed_or_invalid_quote"}, None
    if bps > max_bps:
        return {**base, "action": "skip", "reason": f"spread_above_{max_bps}bps", "spread_bps": str(bps.quantize(Decimal('0.1')))}, None
    limit = ceil_cent(dec(quote["ap"]) * long_mult) if leg == LEG_LONG else floor_cent(dec(quote["bp"]) * short_mult)
    qty, notional, why = sized_qty(ev.get("target_notional"), limit)
    if why:
        return {**base, "action": "skip", "reason": why, "target_notional": str(ev.get("target_notional"))}, None
    why = entry_cap_violation(notional, window_label, leg, ev["symbol"], exposure, limits, account)
    if why:
        return {**base, "action": "skip", "reason": why}, None
    intent = entry_intent(session_date, stage, ev["symbol"], leg, qty, "day", limit, arm=arm, extended=extended)
    commit_entry(exposure, notional, window_label, leg, ev["symbol"])
    return {**base, "action": "enter", "reason": "ok", "qty": qty, "limit_price": str(limit),
            "spread_bps": str(bps.quantize(Decimal("0.1"))), "est_notional": str(notional),
            "target_notional": str(ev.get("target_notional")), "client_order_id": intent["client_order_id"]}, intent


def plan_rth_entry(ev, quote, now, session_date, exposure, limits, account=None):
    """(decision, intent|None) for one scored core RTH event at release + 15 min."""
    return _marketable_entry(ev, quote, now, session_date, exposure, limits, arm=CORE, window_label=RTH,
                             stage=SESSION_CODE[RTH], max_bps=MAX_SPREAD_BPS, long_mult=LONG_LIMIT_MULT,
                             short_mult=SHORT_LIMIT_MULT, extended=False, account=account)


def plan_ext_entry(ev, quote, now, session_date, exposure, limits, arm, account=None):
    """(decision, intent|None) for an exploratory extended-hours entry (arm pm or ah).

    Marketable extended-hours day limit at ask x 1.003 / bid x 0.997; skip over 1% spread
    or without a quote; ev["target_notional"] must already be 25% of the section-A size.
    """
    label = EXT_PRE if arm == PM else EXT_POST
    return _marketable_entry(ev, quote, now, session_date, exposure, limits, arm=arm, window_label=label,
                             stage="ent", max_bps=EXT_MAX_SPREAD_BPS, long_mult=EXT_LONG_LIMIT_MULT,
                             short_mult=EXT_SHORT_LIMIT_MULT, extended=True, account=account)


def arm_for_release(calendar, created_at):
    """PM for a 04:00-09:00 ET release on a session day, AH for 16:00-19:30, else None."""
    t = sig.as_utc(created_at)
    local = t.astimezone(NY)
    if not is_session(calendar, local.date()):
        return None
    s = calendar.get(local.date())
    if local_at(local.date(), 4) <= t < local_at(local.date(), *PM_LAST_RELEASE):
        return PM
    if s.close_utc <= t < local_at(local.date(), *AH_LAST_RELEASE) and not s.early_close:
        return AH
    return None


# ---------------------------------------------------------------------------------------
# Close-out from per-arm ledgers
# ---------------------------------------------------------------------------------------


def _holdings(book, arms, entry_date=None):
    return [(arm, day, sym, qty) for (arm, day, sym), qty in sorted(book.items(), key=lambda kv: (kv[0][0], kv[0][2]))
            if arm in arms and qty != 0 and (entry_date is None or day == entry_date)]


def plan_cls_exits(book, session_date, covered, arms=(CORE, PM)):
    """CLS market exits for today's core/pm holdings not already covered by a live exit."""
    return [exit_intent(day, "cls", sym, qty, arm=arm) for arm, day, sym, qty in _holdings(book, arms, session_date)
            if (arm, sym) not in covered]


def plan_market_flatten(book, session_date, covered, arms=(CORE, PM)):
    """15:55: a day market order for any core/pm holding without a live exit."""
    return [exit_intent(day, "mkt", sym, qty, arm=arm) for arm, day, sym, qty in _holdings(book, arms, session_date)
            if (arm, sym) not in covered]


def plan_ext_flatten(book, quotes, session_date, stage="ext", arms=(CORE, PM)):
    """After the close: extended-hours limit exits at bid -0.5% (sell) or ask +0.5% (buy)."""
    out, missing = [], []
    for arm, day, sym, qty in _holdings(book, arms, session_date):
        q = quotes.get(sym) or {}
        if qty > 0 and q.get("bp"):
            price = floor_cent(dec(q["bp"]) * (1 - EXT_FLATTEN_OFFSET))
        elif qty < 0 and q.get("ap"):
            price = ceil_cent(dec(q["ap"]) * (1 + EXT_FLATTEN_OFFSET))
        else:
            missing.append(sym)
            continue
        out.append(exit_intent(day, stage, sym, qty, limit_price=price, extended=True, arm=arm))
    return out, missing


def plan_ah_opg_exits(book, session_date, calendar):
    """OPG exits in session_date's auction for AH holdings entered on the previous session."""
    prev = calendar.previous(session_date)
    if prev is None:
        return []
    return [exit_intent(day, "opg", sym, qty, arm=AH) for arm, day, sym, qty in _holdings(book, (AH,), prev.session)]


# ---------------------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------------------


def cash_flows(fills):
    """(signed cash flow, sold notional) of filled orders (sells +, buys -)."""
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


realized_pnl = cash_flows  # a flat day's cash flow is its realized P&L


def reconcile(start_cash, end_cash, fills, positions, open_orders, expected=None):
    """End-of-day check: positions equal the expected overnight holdings (none for core/pm),
    no open orders of ours, and the cash change equals the day's fill cash flows within fees.

    expected: {symbol: signed qty} held overnight on purpose (the ah arm), else empty.
    Fee tolerance: SEC Section 31 plus FINRA TAF, bounded by 0.1% of sold notional + $1.
    """
    expected = {s: dec(q) for s, q in (expected or {}).items() if dec(q) != 0}
    flow, sold = cash_flows(fills)
    cash_change = dec(end_cash) - dec(start_cash)
    tolerance = sold * Decimal("0.001") + Decimal("1")
    diff = cash_change - flow
    held = {p["symbol"]: dec(p["qty"]) for p in positions if dec(p["qty"]) != 0}
    problems = []
    unexpected = sorted(s for s in set(held) | set(expected) if held.get(s, 0) != expected.get(s, 0))
    if unexpected:
        problems.append("positions_open")
    if [o for o in open_orders if is_nf1(o.get("client_order_id"))]:
        problems.append("orders_open")
    if abs(diff) > tolerance:
        problems.append("cash_mismatch")
    return {
        "ok": not problems,
        "problems": problems,
        "fill_cash_flow": str(flow),
        "realized_pnl": str(flow) if not expected else None,
        "cash_change": str(cash_change),
        "difference": str(diff),
        "tolerance": str(tolerance),
        "fills": len(fills),
        "unexpected_positions": unexpected,
        "overnight_holdings": {s: str(q) for s, q in expected.items()},
    }


def shadow_times(release_utc, received_utc):
    """Quote snapshots at release (or receipt if later), +15 and +60 minutes."""
    release = sig.as_utc(release_utc)
    first = max(release, sig.as_utc(received_utc))
    return [("release", first), ("plus15", release + timedelta(minutes=15)), ("plus60", release + timedelta(minutes=60))]
