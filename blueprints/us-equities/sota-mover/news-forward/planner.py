"""Pure planning rules for the live news-LLM paper runner (no I/O, no clock reads).

Every rule the historical study preregisters (windows, guards, novelty, lanes, labels)
is taken from ``news_signal.py`` by path; this module adds only the live execution
layer: session labels, the daily schedule, risk-scaled sizing, basket construction,
hard risk caps, per-arm client order ids and ledgers, order intents and
reconciliation arithmetic.

Arms (each with its own client-id prefix and gross cap):
  core  nf1-       execution_test: open auction entry, CLS exit, flat by the close (its study,
                   NEWS-1, failed, so it is not evidence); before the reversal switch date also
                   the momentum RTH entry, afterwards shadow-only (no orders)
  rev   nf1r-      preregistered rth_reversal (../news-reversal/forward-protocol.json): liquid
                   RTH headlines, against the operative label at release + 15 min, marketable
                   limit at the first valid quote's ask/bid within 60 s, CLS exit
  pm    nf1x-pm-   exploratory: 04:00-09:00 liquid headlines, extended-hours entry at
                   release + 15 min, CLS exit
  ah    nf1x-ah-   exploratory: 16:00-19:30 headlines, extended-hours entry at release
                   + 15 min, held overnight, exit at the next session's OPG

Frozen study rules used here by path (``news_signal.py``): windows and guard A, guard B
(``ingestion_guard`` on our own received_at, the study's id-based estimate recorded beside it),
the narrowed D5 movement regex, novelty, lanes, Rule 201 (``ssr_carryover``/``ssr_flag``), the
quote window of ``rth_entry_quote`` and, via the supervisor, the operative D22 label.
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

CORE, PM, AH, REV = "core", "pm", "ah", "rev"
ARM_PREFIX = {CORE: "nf1-", PM: "nf1x-pm-", AH: "nf1x-ah-", REV: "nf1r-"}
# core: the overnight OPG/CLS arm's study (NEWS-1) failed, so its fills are an execution test only.
ARM_LABEL = {CORE: "execution_test", PM: "exploratory", AH: "exploratory", REV: "preregistered_forward"}
ORDER_PREFIX = ARM_PREFIX[CORE]
MAX_NAMES_PER_LEG = 12
# Section A sizing: notional_i = min(0.0015 E / sigma_i, 0.5% MDV20_i, 5% E)
RISK_BUDGET = Decimal("0.0015")
MDV_FRACTION = Decimal("0.005")
MAX_NAME_FRACTION = Decimal("0.05")
MIN_NAME_NOTIONAL = Decimal("1000")
ARM_SIZE_FRACTION = Decimal("0.25")   # exploratory arms trade 25% of the section-A size
ARM_GROSS_FRACTION = Decimal("0.25")  # and each has its own gross cap of 0.25 E
NET_CAP_FRACTION = Decimal("0.10")    # per arm and window: |long - short notional| <= 0.10 E
PLAN_FRACTION = Decimal("0.95")       # OPG baskets are planned at 95% of every cap (M3)
OPG_MAX_SPREAD_BPS = Decimal("100")   # pre-market spread gate for OPG entries (M3)
OPG_BAND = Decimal("0.15")            # OPG reference mid must be within 15% of the prior close (M3)
TRIM_TARGET_FRACTION = Decimal("0.95")  # a net-cap trim brings |net| to 95% of the cap (M4)
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
SSR_TRIGGER = Decimal("1") - Decimal(str(sig.SSR_DECLINE))  # 0.90, the study's Rule 201 decline
# rth_reversal: the first valid SIP quote stamped in [release + 15 min, + 60 s] (news_signal.rth_entry_quote's
# window) prices a marketable limit at its ask (buy) or bid (sell); a working entry is cancelled 60 s after
# submission, so a position exists only if it filled inside the entry minute.
REV_QUOTE_WINDOW = sig.RTH_QUOTE_WINDOW
REV_ENTRY_TTL = sig.RTH_QUOTE_WINDOW
REVERSAL_LEG = {"FAVORABLE": "short", "UNFAVORABLE": "long"}  # against the operative (D22) label

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
    cls_start: datetime        # close - 20 min (15:40): RTH entries stop, CLS exits start
    cls_end: datetime          # close - 15 min (15:45): the study's last RTH entry time
    cls_retry_end: datetime    # close - 11 min (15:49): last CLS (re)submission; Alpaca's cutoff is 15:50
    market_flatten_at: datetime  # close - 5 min (15:55)
    ext_flatten_at: datetime   # close + 2 min
    ext_end: datetime          # 20:00 ET (17:00 on early-close days)
    service_end: datetime      # ext_end + 5 min
    fallback_start: datetime   # open + 1 min: carry-over fallback exits and net-cap trims


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
        cls_retry_end=s.close_utc - timedelta(minutes=11),
        market_flatten_at=s.close_utc - timedelta(minutes=5),
        ext_flatten_at=s.close_utc + timedelta(minutes=2),
        ext_end=ext_end,
        service_end=ext_end + timedelta(minutes=5),
        fallback_start=s.open_utc + timedelta(minutes=1),
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
    """CLS exits are (re)submitted from 15:40 until 15:49 (M1: retried until they are accepted)."""
    return schedule.cls_start <= now <= schedule.cls_retry_end


# ---------------------------------------------------------------------------------------
# Article screening: the study's guards in the study's order (prepare.scan_news)
# ---------------------------------------------------------------------------------------


class Screener:
    """Stateful but I/O-free: the 24-hour novelty tracker and the news-id index.

    Feed every received article (any symbol count) in (created_at, id) order. Returns a
    candidate dict for a single-symbol Benzinga article that passes the study's filters in
    the study's order (prepare.scan_news: relevance and primary operating company, window,
    guard A, D5 movement, novelty, headline year, then guard B), else a drop reason.

    Guard B (the study's F11) compares an ingestion time with the window's decision cutoff
    (news_signal.ingestion_guard). Live, the ingestion time is our own ``received_at`` (the
    article must carry it; the poller stamps it); the study's estimate, max(created_at, p90
    of the created_at of the 100 next-lower news ids seen), is recorded beside it and its
    verdict journaled, but does not decide. The superseded id-order guard is not used.
    """

    def __init__(self, calendar, assets):
        self.calendar = calendar
        self.assets = assets  # symbol -> asset dict (symbol, name, exchange, status, ...)
        self.tracker = sig.DuplicateTracker()
        self._ids = []    # sorted numeric news ids
        self._times = {}  # id -> created_at epoch seconds
        self._last_prune_day = None

    def estimated_ingestion(self, nid, created):
        """The study's guard-B estimate (epoch s) over the next-lower ids seen so far (news_signal.estimated_ingestion)."""
        created_ts = int(created.timestamp())
        if nid is None:
            return created_ts
        pos = bisect.bisect_left(self._ids, nid)
        preds = sorted(self._times[i] for i in self._ids[max(0, pos - sig.INGESTION_PREDECESSORS):pos])
        return sig.estimated_ingestion(preds, created_ts)

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
        try:
            received = sig.as_utc(article["received_at"]) if article.get("received_at") else None
        except (ValueError, TypeError):
            received = None
        if received is None:
            return None, "drop_guard_missing_received_at"  # guard B cannot be evaluated: fail closed
        estimated = self.estimated_ingestion(nid, created)
        est_ok, _ = sig.ingestion_guard(window, estimated)
        ok, reason = sig.ingestion_guard(window, received.timestamp())
        if not ok:
            return None, f"drop_guard_{reason}"
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
            "decision_cutoff_utc": common.iso(window.decision_cutoff_utc),
            "received_at": common.iso(received),
            "ingestion_basis": "received_at",
            "estimated_ingestion_at": common.iso(datetime.fromtimestamp(estimated, common.UTC)),
            "estimated_ingestion_guard_ok": est_ok,
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


def ssr_carryover_from_bars(calendar, trade_session, bars):
    """The study's Rule 201 carry-over (news_signal.ssr_carryover) from daily bars, or None when
    the prior session's low or the close before it is missing (callers fail closed).

    The study uses split-adjusted bars (the prior session's low <= 90% of the close of the
    session before it); pass the split-adjusted bars when available."""
    by_day = bars_by_session(bars)
    prev = calendar.prior_sessions(trade_session, 2)
    if not prev:
        return None
    d2, d1 = prev
    if d1 not in by_day or d2 not in by_day:
        return None
    return sig.ssr_carryover(float(by_day[d1]["l"]), float(by_day[d2]["c"]))


def ssr_active(calendar, trade_session, bars, today_low=None, adj_bars=None):
    """Rule 201 short-sale restriction in force on trade_session, from pre-decision data.

    True when the study's carry-over holds (news_signal.ssr_carryover on the split-adjusted
    bars when given, else on `bars`), or when today's low so far is at least 10% below the
    previous session's raw close (the live check of the day's own trigger). Missing data is
    treated as restricted (fail-closed: no short).
    """
    carry = ssr_carryover_from_bars(calendar, trade_session, adj_bars if adj_bars else bars)
    if carry is None or carry:
        return True
    prev = calendar.prior_sessions(trade_session, 1)
    last = bars_by_session(bars).get(prev[-1]) if prev else None
    if last is None:
        return True
    if today_low is not None and dec(today_low) <= SSR_TRIGGER * dec(last["c"]):
        return True
    return False


def ssr_state(calendar, trade_session, bars, adj_bars=None, entry_quote=None, today_low=None):
    """Rule 201 components for an RTH short decision, fail-closed.

    study_flag: news_signal.ssr_flag for an RTH event (the carry-over, or the entry quote's bid
    <= 90% of the prior session's raw close); session_low_flag: today's low so far <= 90% of
    that close (the live check of the day's own trigger, stricter than the study); data_missing:
    the carry-over inputs or the prior close are unavailable. restricted = any of them.
    """
    carry = ssr_carryover_from_bars(calendar, trade_session, adj_bars if adj_bars else bars)
    prev = calendar.prior_sessions(trade_session, 1)
    last = bars_by_session(bars).get(prev[-1]) if prev else None
    prior_close = float(last["c"]) if last else None
    quote = None
    if entry_quote and entry_quote.get("bp") and entry_quote.get("ap"):
        quote = {"bid": float(entry_quote["bp"]), "ask": float(entry_quote["ap"]), "t": entry_quote.get("t")}
    study = sig.ssr_flag({"ssr_carryover": bool(carry), "window": sig.RTH, "prior_close": prior_close}, quote)
    low_flag = bool(today_low is not None and prior_close and dec(today_low) <= SSR_TRIGGER * dec(prior_close))
    missing = carry is None or prior_close is None
    return {"restricted": bool(missing or study or low_flag), "carryover": carry, "study_flag": bool(study),
            "session_low_flag": low_flag, "data_missing": missing, "prior_close": prior_close,
            "adjusted_bars": bool(adj_bars)}


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


def reversal_leg(label):
    """rth_reversal: FAVORABLE -> short, UNFAVORABLE -> long; UNCLEAR and PARSE_FAIL -> None (no trade)."""
    return REVERSAL_LEG.get(label)


def operative_label(score_row):
    """(label, score, rule) of a scorer row by the study's operative D22 prefix rule
    (news_signal.operative_score on raw_output and stop); the row's stored strict label is not used."""
    return sig.operative_score((score_row or {}).get("raw_output"), (score_row or {}).get("stop"))


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
TERMINAL_STATUSES = ("filled", "canceled", "expired", "replaced", "rejected", "done_for_day", "calculated")


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


def is_live(order):
    """True while the broker may still fill the order (any status that is not final)."""
    return str(order.get("status") or "").lower() not in TERMINAL_STATUSES


def is_entry(info, side):
    """Entries buy a long leg or sell a short leg; exits do the opposite (an exit id names the leg it closes)."""
    return (info["leg"] == LEG_LONG) == (side == "buy")


def window_of(arm, stage):
    if arm == CORE:
        return {"opg": OPEN_AUCTION, "rth": RTH}.get(stage)
    if arm == REV:
        return RTH if stage == "rth" else None
    return EXT_PRE if arm == PM else EXT_POST


def holdings(orders, ref_prices=None):
    """Per (arm, entry_date, symbol) state from our orders (paper: the broker's; dry-run: simulated).

    qty: signed net filled quantity of entries and exits; leg/window: from the entry order;
    entry_qty/entry_notional: filled entry quantity and notional (their ratio is the entry
    price); pending_qty/pending_notional: the unfilled remainder of live entry orders,
    priced at the limit or, for market and OPG orders, at the reference price recorded at
    submission (ref_prices by client_order_id; remainders without a price are counted in
    pending_unpriced); exit_live_qty: the unfilled remainder of live exit orders.
    Rejected, cancelled and expired remainders count nowhere: their notional is released.
    """
    ref_prices = ref_prices or {}
    out = {}
    for o in orders:
        info = parse_cid(o.get("client_order_id"))
        side = o.get("side")
        if info is None or side not in ("buy", "sell"):
            continue
        key = (info["arm"], info["date"], info["symbol"])
        h = out.setdefault(key, {"qty": Decimal("0"), "leg": None, "window": None, "entry_qty": Decimal("0"),
                                 "entry_notional": Decimal("0"), "pending_qty": Decimal("0"),
                                 "pending_notional": Decimal("0"), "pending_unpriced": 0,
                                 "exit_live_qty": Decimal("0"), "entry_orders": 0})
        filled = dec(o.get("filled_qty") or 0)
        h["qty"] += filled if side == "buy" else -filled
        remaining = max(Decimal("0"), dec(o.get("qty") or 0) - filled) if is_live(o) else Decimal("0")
        if is_entry(info, side):
            h["leg"] = info["leg"]
            h["window"] = window_of(info["arm"], info["stage"])
            h["entry_orders"] += 1
            if filled:
                h["entry_qty"] += filled
                h["entry_notional"] += filled * dec(o.get("filled_avg_price") or 0)
            if remaining:
                price = o.get("limit_price") or ref_prices.get(o.get("client_order_id"))
                h["pending_qty"] += remaining
                if price:
                    h["pending_notional"] += remaining * dec(price)
                else:
                    h["pending_unpriced"] += 1
        else:
            h["exit_live_qty"] += remaining
            if h["leg"] is None:
                h["leg"] = info["leg"]
    return out


def entry_price(h):
    return h["entry_notional"] / h["entry_qty"] if h["entry_qty"] else None


def simulated_positions(hs):
    """Broker-style positions (net qty per symbol) from holdings (dry-run)."""
    net = {}
    for (_arm, _day, sym), h in hs.items():
        net[sym] = net.get(sym, Decimal("0")) + h["qty"]
    return [{"symbol": s, "qty": str(q)} for s, q in sorted(net.items()) if q]


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
    """Close (part of) an arm's holding; the id's leg is the side being closed.

    Stages carry a round number when they can repeat (cls<n>, mkt<n>, ext<n>, kill<n>,
    xopg<n> for carry-over auction exits, cof<n> for their post-open fallback, trim<n>,
    xca<n>); the default TIF is cls for cls*, opg for xopg*, else day.
    """
    qty = dec(position_qty)
    leg = LEG_LONG if qty > 0 else LEG_SHORT
    tif = tif or ("cls" if stage.startswith("cls") else "opg" if stage.startswith("xopg") else "day")
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
    """Per-arm caps: gross = L x E (core and rev) or 0.25 E (each exploratory arm); per order
    = 5% E; net = |long - short| notional per window <= 0.10 E."""
    equity: Decimal
    gross_cap: Decimal
    per_order_cap: Decimal
    net_cap: Decimal

    @classmethod
    def for_arm(cls, arm, equity, leverage, extra_cap=None):
        e = dec(equity)
        gross = dec(leverage) * e if arm in (CORE, REV) else ARM_GROSS_FRACTION * e
        if extra_cap is not None:
            gross = min(gross, dec(extra_cap))
        return cls(e, gross, MAX_NAME_FRACTION * e, NET_CAP_FRACTION * e)

    def scaled(self, fraction):
        """Planning limits: every cap times `fraction` (M3: OPG baskets are sized to 95% of every cap)."""
        f = dec(fraction)
        return Limits(self.equity, self.gross_cap * f, self.per_order_cap * f, self.net_cap * f)


@dataclass
class Exposure:
    gross: Decimal = Decimal("0")
    names: dict = field(default_factory=dict)     # (window_label, leg) -> count
    symbols: set = field(default_factory=set)     # symbols this arm holds or has pending today
    notional: dict = field(default_factory=dict)  # (window_label, leg) -> committed entry notional


def window_net(exposure, window_label):
    """Committed long minus short entry notional of one arm's window."""
    return (exposure.notional.get((window_label, LEG_LONG), Decimal("0"))
            - exposure.notional.get((window_label, LEG_SHORT), Decimal("0")))


def net_headroom(exposure, window_label, leg, limits):
    """Largest new entry on `leg` that keeps |long - short| <= net_cap in this window."""
    net = window_net(exposure, window_label)
    return limits.net_cap - net if leg == LEG_LONG else limits.net_cap + net


def exposure_from(hs, arm, day, unpriced_notional):
    """Fill-based exposure of one arm's entries on `day` (M4).

    Each holding counts its current filled quantity at its entry price plus its working
    entry remainder (limit or reference price; an unpriced remainder counts at
    `unpriced_notional`, the per-order cap). Rejected, cancelled or expired entries
    without a fill release their notional; their symbol still blocks a repeat entry.
    """
    x = Exposure()
    for (a, d, sym), h in hs.items():
        if a != arm or d != day or h["window"] is None:
            continue
        x.symbols.add(sym)
        avg = entry_price(h) or Decimal("0")
        notional = abs(h["qty"]) * avg + h["pending_notional"] + dec(unpriced_notional) * h["pending_unpriced"]
        if h["entry_qty"] == 0 and notional == 0:
            continue
        key = (h["window"], h["leg"])
        x.gross += notional
        x.names[key] = x.names.get(key, 0) + 1
        x.notional[key] = x.notional.get(key, Decimal("0")) + notional
    return x


def copy_exposure(x):
    return Exposure(x.gross, dict(x.names), set(x.symbols), dict(x.notional))


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
    exposure.notional[key] = exposure.notional.get(key, Decimal("0")) + dec(notional)
    exposure.symbols.add(symbol)


def apply_net_cap(rows, net_cap, fixed_long=Decimal("0"), fixed_short=Decimal("0"), max_rounds=10):
    """Scale the larger leg's new names down pro rata until |long - short| <= net_cap.

    rows: new names (dicts with symbol, leg, price, qty, notional). fixed_long/short:
    notional already committed in this window (never rescaled). Each round multiplies
    the larger leg's new names by (smaller total + net_cap - larger fixed) / larger new
    total, floors to whole shares and drops a name that falls below one share or $1,000
    (reason net_cap_below_min). Rounds repeat only if drops flip the imbalance; when
    the larger leg has no new names left, the smaller leg's new names are kept (each
    reduces the imbalance) and the loop stops. An imbalance still unresolved after
    max_rounds drops every new name (fail closed). Returns (kept, dropped, record) with
    the pre-cap and post-cap leg notionals for the journal.
    """
    rows = [dict(r) for r in rows]
    fixed = {LEG_LONG: dec(fixed_long), LEG_SHORT: dec(fixed_short)}

    def new_total(rs, leg):
        return sum((r["notional"] for r in rs if r["leg"] == leg), Decimal("0"))

    def totals(rs):
        return fixed[LEG_LONG] + new_total(rs, LEG_LONG), fixed[LEG_SHORT] + new_total(rs, LEG_SHORT)

    pre_long, pre_short = totals(rows)
    dropped, factors = [], []
    while True:
        long_total, short_total = totals(rows)
        if abs(long_total - short_total) <= net_cap:
            break
        big = LEG_LONG if long_total > short_total else LEG_SHORT
        big_new = new_total(rows, big)
        if big_new <= 0:
            break  # the imbalance is already-committed exposure; new names only reduce it
        if len(factors) >= max_rounds:
            dropped.extend((r, "net_cap_unresolved") for r in rows)
            rows = []
            break
        allowed = max(Decimal("0"), min(long_total, short_total) + net_cap - fixed[big])
        factors.append(allowed / big_new)
        kept = []
        for r in rows:
            if r["leg"] != big:
                kept.append(r)
                continue
            # multiply before dividing so an exact pro-rata share is not floored a share short
            qty = whole_qty(r["notional"] * allowed / big_new, r["price"])
            notional = dec(qty) * dec(r["price"])
            if qty < 1 or notional < MIN_NAME_NOTIONAL:
                dropped.append((r, "net_cap_below_min"))
                continue
            kept.append({**r, "qty": qty, "notional": notional})
        rows = kept
    post_long, post_short = totals(rows)
    record = {
        "net_cap": str(net_cap),
        "committed": {"long": str(fixed[LEG_LONG]), "short": str(fixed[LEG_SHORT])},
        "pre_cap": {"long": str(pre_long), "short": str(pre_short), "net": str(pre_long - pre_short)},
        "post_cap": {"long": str(post_long), "short": str(post_short), "net": str(post_long - post_short)},
        "scale_factors": [str(f.quantize(Decimal("0.000001"))) for f in factors],
        "dropped": [{"symbol": r["symbol"], "reason": why} for r, why in dropped],
    }
    return rows, dropped, record


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
    """(decisions, OPG intents, net-cap record) for scored overnight events of one session.

    events: dicts with symbol, created_at, news_id, lane, label, quote (pre-market SIP
    bp/ap), prior_close, asset, ssr and target_notional (section A size). Only the liquid
    lane trades; FAVORABLE goes long; UNFAVORABLE goes short only when shortable, easy to
    borrow and not under Rule 201. Pre-market gates (M3): a two-sided quote, spread at most
    100 bps and a mid within 15% of the prior close; the mid is the reference price. Each
    leg takes its first 12 names by (created_at, news_id); every cap is applied at 95%
    (M3: an auction fill may differ from the reference): names are sized to at most 95% of
    the per-order cap and gross is filled in release order up to 95% of the arm's and the
    account's caps; then the net cap (95% of 0.10 E, apply_net_cap) scales the larger leg
    down pro rata. A leg with fewer than 2 names may trade alone, but only inside the net
    cap (coordinator amendment 2026-09-25; it replaces the study's 2-name leg minimum for
    execution). ``blocked``: symbols with a carry-over position exiting in the same
    auction. account_gross: optional [total gross of all arms, account cap], updated in
    place.
    """
    plan = limits.scaled(PLAN_FRACTION)
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
            decisions.append({**base, "leg": leg, "action": "skip", "reason": "symbol_exiting_carry_over_position"})
            continue
        if leg == LEG_SHORT:
            ok, why = short_allowed(ev.get("asset"), ev.get("ssr", True))
            if not ok:
                decisions.append({**base, "leg": leg, "action": "skip", "reason": why})
                continue
        if not (ev.get("asset") or {}).get("tradable", False):
            decisions.append({**base, "leg": leg, "action": "skip", "reason": "not_tradable"})
            continue
        quote = ev.get("quote") or {}
        bps = spread_bps(quote["bp"], quote["ap"]) if quote.get("bp") and quote.get("ap") else None
        if bps is None:
            decisions.append({**base, "leg": leg, "action": "skip", "reason": "no_premarket_quote"})
            continue
        if bps > OPG_MAX_SPREAD_BPS:
            decisions.append({**base, "leg": leg, "action": "skip", "reason": "premarket_spread_above_100bps",
                              "spread_bps": str(bps.quantize(Decimal("0.1")))})
            continue
        mid = (dec(quote["bp"]) + dec(quote["ap"])) / 2
        prior = ev.get("prior_close")
        if not prior or dec(prior) <= 0 or abs(mid / dec(prior) - 1) > OPG_BAND:
            decisions.append({**base, "leg": leg, "action": "skip", "reason": "mid_outside_15pct_of_prior_close",
                              "mid": str(mid), "prior_close": str(prior)})
            continue
        if len(legs[leg]) >= MAX_NAMES_PER_LEG:
            decisions.append({**base, "leg": leg, "action": "skip", "reason": "names_per_leg_cap"})
            continue
        legs[leg].append(({**ev, "ref_price": mid, "spread_bps": str(bps.quantize(Decimal("0.1")))}, base))
    chosen = {LEG_LONG: [], LEG_SHORT: []}
    queue = sorted([(ev["created_at"], leg, ev, base) for leg in legs for ev, base in legs[leg]], key=lambda x: x[0])
    trial = copy_exposure(exposure)
    trial_account = [account_gross[0], dec(account_gross[1]) * PLAN_FRACTION] if account_gross is not None else None
    for _, leg, ev, base in queue:
        target = ev.get("target_notional")
        target = None if target is None else min(dec(target), plan.per_order_cap)
        qty, notional, why = sized_qty(target, ev["ref_price"])
        if why:
            decisions.append({**base, "leg": leg, "action": "skip", "reason": why,
                              "target_notional": str(ev.get("target_notional"))})
            continue
        why = entry_cap_violation(notional, OPEN_AUCTION, leg, ev["symbol"], trial, plan, trial_account)
        if why:
            decisions.append({**base, "leg": leg, "action": "skip", "reason": why})
            continue
        commit_entry(trial, notional, OPEN_AUCTION, leg, ev["symbol"])
        if trial_account is not None:
            trial_account[0] = dec(trial_account[0]) + notional
        chosen[leg].append((ev, base, qty, notional))
    rows = [{"symbol": ev["symbol"], "leg": leg, "price": dec(ev["ref_price"]), "qty": qty, "notional": notional,
             "pre_cap_qty": qty, "pre_cap_notional": notional, "ev": ev, "base": base}
            for leg in (LEG_LONG, LEG_SHORT) for ev, base, qty, notional in chosen[leg]]
    # the window's already-committed entries (e.g. after a restart) count, unscaled, toward the net cap
    kept, dropped, record = apply_net_cap(
        rows, plan.net_cap,
        fixed_long=exposure.notional.get((OPEN_AUCTION, LEG_LONG), Decimal("0")),
        fixed_short=exposure.notional.get((OPEN_AUCTION, LEG_SHORT), Decimal("0")))
    record = {**record, "arm": CORE, "window": OPEN_AUCTION, "hard_net_cap": str(limits.net_cap),
              "plan_fraction": str(PLAN_FRACTION)}
    for r, why in dropped:
        decisions.append({**r["base"], "leg": r["leg"], "action": "skip", "reason": why,
                          "pre_cap_notional": str(r["pre_cap_notional"])})
    intents = []
    for r in kept:
        ev, base, leg, qty, notional = r["ev"], r["base"], r["leg"], r["qty"], r["notional"]
        intent = entry_intent(session_date, SESSION_CODE[OPEN_AUCTION], ev["symbol"], leg, qty, "opg")
        decisions.append({**base, "leg": leg, "action": "enter", "reason": "ok", "qty": qty,
                          "ref_price": str(ev["ref_price"]), "spread_bps": ev.get("spread_bps"),
                          "pre_cap_qty": r["pre_cap_qty"], "pre_cap_notional": str(r["pre_cap_notional"]),
                          "est_notional": str(notional), "target_notional": str(ev.get("target_notional")),
                          "sigma": ev.get("sigma"), "client_order_id": intent["client_order_id"]})
        intents.append(intent)
        commit_entry(exposure, notional, OPEN_AUCTION, leg, ev["symbol"])
        if account_gross is not None:
            account_gross[0] = dec(account_gross[0]) + notional
    return decisions, intents, record


# ---------------------------------------------------------------------------------------
# Regular-session entries (release + 15 min, marketable limit on the latest SIP quote)
# ---------------------------------------------------------------------------------------


def spread_bps(bid, ask):
    bid, ask = dec(bid), dec(ask)
    if bid <= 0 or ask <= 0 or ask < bid:
        return None
    return (ask - bid) / ((ask + bid) / 2) * Decimal("10000")


def quote_fields(quote):
    """The decision quote as journaled (bid, ask, stamp, mid); empty without a two-sided quote."""
    q = quote or {}
    if not q.get("bp") or not q.get("ap"):
        return {}
    return {"quote_bid": str(dec(q["bp"])), "quote_ask": str(dec(q["ap"])), "quote_t": q.get("t"),
            "quote_mid": str((dec(q["bp"]) + dec(q["ap"])) / 2)}


def _marketable_entry(ev, quote, now, session_date, exposure, limits, *, arm, window_label, stage, max_bps,
                      long_mult, short_mult, extended, account=None, leg_for=side_for_label, grace=RTH_ENTRY_GRACE,
                      quote_window=None):
    """(decision, intent|None) for one scored event at its entry time.

    leg_for maps the label to a leg; the entry may happen until entry + grace. With
    quote_window, the quote must be stamped in [entry, entry + quote_window] (the study's
    rth_entry_quote window): an older quote means "wait" for a fresher one.
    """
    base = {"event_id": ev.get("event_id"), "symbol": ev["symbol"], "session_label": window_label,
            "lane": ev.get("lane"), "label": ev.get("label"), "arm": arm}
    if ev.get("lane") != sig.LIQUID:
        return {**base, "action": "shadow", "reason": f"lane_{ev.get('lane')}_shadow_only"}, None
    leg = leg_for(ev.get("label"))
    if leg is None:
        return {**base, "action": "skip", "reason": f"label_{str(ev.get('label')).lower()}"}, None
    base["leg"] = leg
    entry = sig.as_utc(ev["entry_utc"])
    if now < entry:
        return {**base, "action": "wait", "reason": "before_entry_time"}, None
    if now - entry > grace:
        return {**base, "action": "skip", "reason": "entry_late"}, None
    if leg == LEG_SHORT:
        ok, why = short_allowed(ev.get("asset"), ev.get("ssr", True))
        if not ok:
            return {**base, "action": "skip", "reason": why}, None
    if not (ev.get("asset") or {}).get("tradable", False):
        return {**base, "action": "skip", "reason": "not_tradable"}, None
    if not quote or not quote.get("bp") or not quote.get("ap"):
        return {**base, "action": "skip", "reason": "no_two_sided_quote"}, None
    base.update(quote_fields(quote))
    if quote_window is not None:
        try:
            stamped = sig.as_utc(quote["t"]) if quote.get("t") else None
        except (ValueError, TypeError):
            stamped = None
        if stamped is None:
            return {**base, "action": "skip", "reason": "quote_without_timestamp"}, None
        if stamped < entry:
            return {**base, "action": "wait", "reason": "quote_before_entry_time"}, None
        if stamped > entry + quote_window:
            return {**base, "action": "skip", "reason": "quote_after_entry_window"}, None
    bps = spread_bps(quote["bp"], quote["ap"])
    if bps is None:
        return {**base, "action": "skip", "reason": "crossed_or_invalid_quote"}, None
    if bps > max_bps:
        return {**base, "action": "skip", "reason": f"spread_above_{max_bps}bps", "spread_bps": str(bps.quantize(Decimal('0.1')))}, None
    limit = ceil_cent(dec(quote["ap"]) * long_mult) if leg == LEG_LONG else floor_cent(dec(quote["bp"]) * short_mult)
    qty, notional, why = sized_qty(ev.get("target_notional"), limit)
    if why:
        return {**base, "action": "skip", "reason": why, "target_notional": str(ev.get("target_notional"))}, None
    pre_qty, pre_notional = qty, notional
    headroom = net_headroom(exposure, window_label, leg, limits)
    net_before = window_net(exposure, window_label)
    if notional > headroom:  # the window's net cap: shrink to the headroom, keeping the minimums
        qty = whole_qty(max(headroom, Decimal("0")), limit)
        notional = dec(qty) * limit
        if qty < 1 or notional < MIN_NAME_NOTIONAL:
            return {**base, "action": "skip", "reason": "net_exposure_cap", "pre_cap_notional": str(pre_notional),
                    "net_before": str(net_before), "net_cap": str(limits.net_cap)}, None
    why = entry_cap_violation(notional, window_label, leg, ev["symbol"], exposure, limits, account)
    if why:
        return {**base, "action": "skip", "reason": why}, None
    intent = entry_intent(session_date, stage, ev["symbol"], leg, qty, "day", limit, arm=arm, extended=extended)
    commit_entry(exposure, notional, window_label, leg, ev["symbol"])
    return {**base, "action": "enter", "reason": "ok", "qty": qty, "limit_price": str(limit),
            "spread_bps": str(bps.quantize(Decimal("0.1"))), "pre_cap_qty": pre_qty,
            "pre_cap_notional": str(pre_notional), "est_notional": str(notional),
            "net_before": str(net_before), "net_after": str(window_net(exposure, window_label)),
            "net_cap": str(limits.net_cap), "target_notional": str(ev.get("target_notional")),
            "client_order_id": intent["client_order_id"]}, intent


def plan_rth_entry(ev, quote, now, session_date, exposure, limits, account=None):
    """(decision, intent|None) for one scored core (momentum) RTH event at release + 15 min (pilot days)."""
    return _marketable_entry(ev, quote, now, session_date, exposure, limits, arm=CORE, window_label=RTH,
                             stage=SESSION_CODE[RTH], max_bps=MAX_SPREAD_BPS, long_mult=LONG_LIMIT_MULT,
                             short_mult=SHORT_LIMIT_MULT, extended=False, account=account)


def plan_rth_reversal_entry(ev, quote, now, session_date, exposure, limits, account=None):
    """(decision, intent|None) for the preregistered rth_reversal arm (forward-protocol.json rule).

    Liquid lane only; against the operative label (FAVORABLE -> short, UNFAVORABLE -> long;
    UNCLEAR and PARSE_FAIL -> no trade); at release + 15 min, on the first quote stamped in
    [entry, entry + 60 s]: a marketable day limit at its ask (buy) or bid (sell), skipped
    above a 50 bps spread; shorts need shortable, easy-to-borrow and no Rule 201 flag
    (ev["ssr"]); section-A size, the rev arm's caps and its RTH window's net cap.
    """
    return _marketable_entry(ev, quote, now, session_date, exposure, limits, arm=REV, window_label=RTH,
                             stage=SESSION_CODE[RTH], max_bps=MAX_SPREAD_BPS, long_mult=Decimal("1"),
                             short_mult=Decimal("1"), extended=False, account=account, leg_for=reversal_leg,
                             grace=REV_QUOTE_WINDOW, quote_window=REV_QUOTE_WINDOW)


def plan_rth_momentum_shadow(ev, quote, now, session_date, exposure, limits):
    """The momentum decision on the same event and quote, for comparison only (never an order).

    Mirror of plan_rth_reversal_entry with the label's own direction (FAVORABLE -> long,
    UNFAVORABLE -> short) at the same touch; the caller passes a shadow exposure so the
    shadow never consumes the real arms' caps.
    """
    return _marketable_entry(ev, quote, now, session_date, exposure, limits, arm=CORE, window_label=RTH,
                             stage=SESSION_CODE[RTH], max_bps=MAX_SPREAD_BPS, long_mult=Decimal("1"),
                             short_mult=Decimal("1"), extended=False, leg_for=side_for_label,
                             grace=REV_QUOTE_WINDOW, quote_window=REV_QUOTE_WINDOW)


def plan_ext_entry(ev, quote, now, session_date, exposure, limits, arm, account=None):
    """(decision, intent|None) for an exploratory extended-hours entry (arm pm or ah).

    Marketable extended-hours day limit at ask x 1.003 / bid x 0.997; skip over 1% spread
    or without a quote; ev["target_notional"] must already be 25% of the section-A size.
    """
    label = EXT_PRE if arm == PM else EXT_POST
    return _marketable_entry(ev, quote, now, session_date, exposure, limits, arm=arm, window_label=label,
                             stage="ent", max_bps=EXT_MAX_SPREAD_BPS, long_mult=EXT_LONG_LIMIT_MULT,
                             short_mult=EXT_SHORT_LIMIT_MULT, extended=True, account=account)


def first_in_window(candidates, cand):
    """True when `cand` is the earliest (created_at, news_id) candidate of its (symbol, session,
    window) among `candidates` (the study's F13, news_signal.first_per_window). Guard B makes
    this decidable at the entry time: an earlier-created candidate that passes guard B was
    received by its own cutoff, which precedes this candidate's entry time."""
    same = [c for c in candidates if c["symbol"] == cand["symbol"] and c["session"] == cand["session"]
            and c.get("window") == cand.get("window")]
    firsts = sig.first_per_window(same)
    return bool(firsts) and firsts[0]["event_id"] == cand["event_id"]


def overnight_hold_allowed(calendar, day):
    """True only when the next XNYS session is the next calendar day.

    The ah arm holds one night at most: Fridays and days before an exchange holiday
    (the next session is two or more days away) are refused, as is a non-session day,
    so no position is held across a weekend or holiday.
    """
    try:
        i = calendar.index_of(day)
    except KeyError:
        return False
    if i + 1 >= len(calendar.sessions):
        return False
    return calendar.sessions[i + 1].session == day + timedelta(days=1)


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
# Close-out: exits from per-holding state, capped at the broker position (M5, m3)
# ---------------------------------------------------------------------------------------


def exit_availability(hs, positions):
    """{symbol: broker net qty left after the unfilled remainder of our working exits}."""
    avail = {p["symbol"]: dec(p["qty"]) for p in positions}
    for (_arm, _day, sym), h in hs.items():
        if h["exit_live_qty"]:
            sign = 1 if h["leg"] == LEG_LONG else -1
            avail[sym] = avail.get(sym, Decimal("0")) - sign * h["exit_live_qty"]
    return avail


def cap_exits(requests, hs, positions):
    """Cap requested exits [(key, signed qty)] so no exit can oversell into a new position.

    Each exit is limited to the holding's part not already covered by a working exit and
    to the broker's position left after all working exits (m3). Returns (exits, notes);
    a note records every cap and every holding the broker no longer shows.
    """
    avail = exit_availability(hs, positions)
    out, notes = [], []
    for key, want in requests:
        h = hs[key]
        want = dec(want)
        if want == 0:
            continue
        sign = 1 if want > 0 else -1
        uncovered = abs(h["qty"]) - h["exit_live_qty"]
        room = avail.get(key[2], Decimal("0")) * sign
        x = min(abs(want), uncovered, room)
        if x <= 0:
            if room <= 0 and uncovered > 0:
                notes.append({"arm": key[0], "entry_date": key[1].isoformat(), "symbol": key[2], "ledger_qty": str(h["qty"]),
                              "available": str(avail.get(key[2], Decimal("0"))), "note": "broker_position_missing"})
            continue
        if x < abs(want):
            notes.append({"arm": key[0], "entry_date": key[1].isoformat(), "symbol": key[2], "wanted": str(want),
                          "capped_to": str(sign * x), "note": "capped_at_broker_position"})
        out.append((key, sign * x))
        avail[key[2]] = avail.get(key[2], Decimal("0")) - sign * x
    return out, notes


def nf1_positions(hs, positions):
    """[(key, signed qty)] of our holdings the broker still shows (working exits ignored)."""
    broker = {p["symbol"]: dec(p["qty"]) for p in positions}
    out = []
    for key, h in sorted(hs.items(), key=lambda kv: (kv[0][1], kv[0][0], kv[0][2])):
        q, b = h["qty"], broker.get(key[2], Decimal("0"))
        if q == 0 or b == 0 or (q > 0) != (b > 0):
            continue
        sign = 1 if q > 0 else -1
        x = min(abs(q), abs(b))
        out.append((key, sign * x))
        broker[key[2]] = b - sign * x
    return out


def exit_plan(hs, positions, include):
    """Exits for every holding selected by include(key, h), whatever its entry date (M5):
    the uncovered part of each, oldest entry first, capped at the broker position."""
    requests = [(key, h["qty"]) for key, h in sorted(hs.items(), key=lambda kv: (kv[0][1], kv[0][0], kv[0][2]))
                if h["qty"] != 0 and include(key, h)]
    return cap_exits(requests, hs, positions)


def marketable_exit_price(qty, quote=None, last_trade=None, offset=EXT_FLATTEN_OFFSET):
    """Limit that closes `qty` (a signed holding) at once: sell a long at bid - offset, buy a
    short back at ask + offset. A missing side falls back to the last trade price (B1);
    None when neither exists (the caller retries at its next round)."""
    q = quote or {}
    if dec(qty) > 0:
        ref = q.get("bp") or last_trade
        return floor_cent(dec(ref) * (1 - offset)) if ref else None
    ref = q.get("ap") or last_trade
    return ceil_cent(dec(ref) * (1 + offset)) if ref else None


def window_net_filled(hs, arm, day, window):
    """(long, short, pending entries) of one arm-window's current filled holdings at entry prices."""
    long_n = short_n = Decimal("0")
    pending = 0
    for (a, d, _sym), h in hs.items():
        if a != arm or d != day or h["window"] != window:
            continue
        pending += 1 if (h["pending_qty"] or h["pending_unpriced"]) else 0
        avg = entry_price(h) or Decimal("0")
        if h["qty"] > 0:
            long_n += h["qty"] * avg
        elif h["qty"] < 0:
            short_n += -h["qty"] * avg
    return long_n, short_n, pending


def plan_net_trim(hs, arm, day, window, net_cap):
    """Trims [(key, signed qty)] that bring an arm-window's filled |long - short| to 95% of
    the net cap, taken pro rata from the larger leg (M4: e.g. after an OPG leg was
    rejected or unfilled). Nothing while entries in the window are still working."""
    long_n, short_n, pending = window_net_filled(hs, arm, day, window)
    net = long_n - short_n
    record = {"arm": arm, "window": window, "long": str(long_n), "short": str(short_n), "net": str(net),
              "net_cap": str(net_cap), "pending_entries": pending}
    if pending:
        return [], {**record, "status": "entries_pending"}
    if any(h["exit_live_qty"] for k, h in hs.items() if k[0] == arm and k[1] == day and h["window"] == window):
        return [], {**record, "status": "exits_working"}
    if abs(net) <= net_cap:
        return [], {**record, "status": "within_cap"}
    sign = 1 if net > 0 else -1
    big = [(k, h) for k, h in sorted(hs.items()) if k[0] == arm and k[1] == day and h["window"] == window
           and h["qty"] * sign > 0]
    big_total = sum((abs(h["qty"]) * entry_price(h) for _, h in big), Decimal("0"))
    excess = abs(net) - dec(net_cap) * TRIM_TARGET_FRACTION
    out = []
    for key, h in big:
        avg = entry_price(h)
        share = excess * abs(h["qty"]) * avg / big_total
        qty = min(abs(h["qty"]), (share / avg).to_integral_value(rounding=ROUND_UP))
        if qty > 0:
            out.append((key, sign * qty))
    return out, {**record, "status": "trim", "excess": str(excess)}


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
