#!/usr/bin/env python3
"""As-of re-fetch of the mover-early-entry coverage misses, run under plan.json (mover-coverage-asof-20260929).

  python refetch.py gate     --inputs DIR --out-dir RUN
  python refetch.py fetch    --env-file ENV --out-dir RUN
  python refetch.py e2       --package-zip ZIP --env-file ENV --out-dir RUN
  python refetch.py classify --out-dir RUN [--inputs DIR] [--verify]
  python refetch.py publish  --run-dir RUN [--e2-dir DIR] --to SUMMARY.json

gate (no network) checks plan.json and the three private inputs by sha256, reproduces
mover-early-entry evaluate.coverage() and writes the 96 missed and 498 control events.
fetch (E1) collects name changes with broad-universe corporate_actions.py, then requests F1 (asof =
the event date) and F2 (asof = 2026-09-21) for those 594 events, plus the KOD/LFCR positive control.
e2 is the secondary estimand: the package events dated 2021-01-04..2025-12-31, with symbols tried in
audit load_events order. classify (no network) applies the frozen touch rule, the reason classes,
flags and labels, and writes per-event results (private) and totals; --verify recomputes the files
and compares their bytes. publish writes the totals-only summary for git.

Market data only: every price request goes to extreme-gainer-audit audit.py DATA_URL on a
/v2/stocks/{symbol}/bars or /auctions path, and E1's name changes come from GET /v1/corporate-actions
through broad-universe corporate_actions.py. Nothing here calls a model.
"""
from __future__ import annotations

import argparse
import csv
import functools
import gzip
import hashlib
import http.client
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections import Counter
from datetime import date, datetime
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
US = HERE.parent
ROOT = US.parents[1]
PLAN_PATH = HERE / "plan.json"
PLAN_BYTES = PLAN_PATH.read_bytes()
PLAN_SHA256 = hashlib.sha256(PLAN_BYTES).hexdigest()
PLAN = json.loads(PLAN_BYTES)


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audit = _load("mover_coverage_asof_audit", US / "extreme-gainer-audit" / "audit.py")
sessions_io = _load("mover_coverage_asof_sessions_io", US / "mover-early-entry" / "sessions_io.py")

WINDOW = ("2021-01-04", "2025-12-31")        # reproduction_gate.rule; dev_val's lo and hi (evaluate.py:682)
HOLDOUT = ("2026-01-02", "2026-09-18")       # guards.holdout (mover-early-entry protocol.json splits)
NAMING_ASOF = "2026-09-21"                   # requests.F2_today_symbol_leg
RENAME_RANGE = ("2021-01-01", "2026-09-21")  # requests.renames
CONTROL_SYMBOLS = ("KOD", "LFCR")            # requests.positive_control
CONTROL_SESSION, CONTROL_START = "2026-09-28", "2026-09-21"
ET = ZoneInfo("America/New_York")
CONTROL_NOT_BEFORE = datetime(2026, 9, 28, 20, 0, tzinfo=ET)
LOOKBACK, AUCTION_LOOKBACK, FORWARD = 60, 22, 5  # sessions (inputs.session_calendar.use)
TOUCH = 1.2  # candidates.py --touch default, which its SQL formats as a literal (candidates.py:43)
MIN_GAIN_PCT = 20
RATIOS = (("3/2", Fraction(3, 2)), ("2", Fraction(2)), ("3", Fraction(3)))  # labels.ratios
CLASS_ORDER = ("fetch_error", "no_asof_event_row", "derivative_pattern", "no_prior_row", "below_touch_split_basis",
               "below_touch_auction_outside_bar_range", "below_touch_other", "recovered_rename_on_event_date",
               "recovered_keyed_under_successor", "recovered_today_symbol_other_issuer",
               "recovered_today_symbol_no_row", "recovered_today_symbol_same_issuer", "recovered_cause_unexplained")
IDENTITY_OUTCOMES = ("f1_raw_unavailable", "f2_error", "f2_not_fetched", "no_row", "other_issuer", "same_issuer")
FLAG_NAMES = ("basis_uncertain", "gap_over_7_days", "leg_error", "not_verified_in_new_vintage", "otc_as_known",
              "prior_row_not_previous_session")
F1_LEGS = ("bars_raw", "bars_split", "bars_all", "auctions")
F2_LEG = "f2_bars_raw"
GAIN_LEGS = ("bars_raw", "bars_split", "auctions")  # the legs audit.event_gain reads
PRICE_PATH = re.compile(r"/v2/stocks/[^/?]+/(bars|auctions)")
NAME_CHANGE_KINDS = ("name_change", "name_changes")  # singular today, plural in older envelopes (coverage.py:135-138)
CALENDAR = PLAN["inputs"]["session_calendar"]
COMMITTED_SUMMARY = US / "mover-early-entry" / "evidence" / "summary-dev-val-run-v1.json"
INPUT_KEYS = ("audit_results", "candidates_main", "candidates_premarket")
TIMESTAMP_KEYS = ("fetched_at_utc", "control_sent_at_utc", "finished_at_utc")
SNAPSHOT_FILES = ("snapshot-f1.json", "snapshot-f2.json", "control.json", "request-log.json")
CLASSIFY_OUTPUTS = ("results.json", "labels.json", "summary.json")
CODE_FILES = tuple(str(p.relative_to(ROOT)) for p in (
    HERE / "refetch.py", PLAN_PATH, US / "extreme-gainer-audit" / "audit.py", US / "extreme-gainer-audit" / "plan.json",
    US / "mover-early-entry" / "evaluate.py", US / "mover-early-entry" / "rules.py",
    US / "mover-early-entry" / "sessions_io.py", US / "mover-early-entry" / "protocol.json",
    US / "mover-early-entry" / "fees.json", COMMITTED_SUMMARY, US / "broad-universe" / "corporate_actions.py",
    US / "broad-universe" / "collect_daily.py", ROOT / CALENDAR["path"]))


class Refused(Exception):
    """A stop before anything unsafe or unverified happens; recorded with its reason, never retried silently."""

    def __init__(self, reason: str, **detail):
        super().__init__(reason)
        self.reason, self.detail = reason, detail


def plan_guard() -> None:
    """freeze_record: nothing is fetched, classified or summarized under a plan.json other than the one loaded."""
    if hashlib.sha256(PLAN_PATH.read_bytes()).hexdigest() != PLAN_SHA256:
        raise Refused("plan_changed")


@functools.lru_cache(maxsize=None)
def mover_modules():
    """mover-early-entry evaluate.py (coverage only) and the rules.py it uses. Both import numpy, so they load on
    demand; evaluate.py imports rules and sessions_io by bare name (evaluate.py:32-34)."""
    folder = str(US / "mover-early-entry")
    if folder not in sys.path:
        sys.path.insert(0, folder)
    evaluate = _load("mover_coverage_asof_evaluate", US / "mover-early-entry" / "evaluate.py")
    return evaluate, evaluate.R


# ----------------------------------------------------------------------------- private files

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path) -> str:
    return sha256_bytes(Path(path).read_bytes())


def private_dir(path) -> Path:
    """A 0700 directory (audit.py:366); the unit runs under UMask=0077, so created parents are 0700 too."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path, 0o700)
    return path


def write_private_bytes(path, data: bytes) -> str:
    """audit.write_private (audit.py:47-57) for bytes: created 0600, with no world-readable window."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as handle:
            fd = None
            handle.write(data)
    finally:
        if fd is not None:
            os.close(fd)
    return sha256_bytes(data)


def dumps(doc) -> bytes:
    return (json.dumps(doc, indent=1, sort_keys=True) + "\n").encode()


def write_doc(path, doc) -> str:
    return write_private_bytes(path, dumps(doc))


def read_doc(path) -> dict:
    return json.loads(Path(path).read_text())


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rnd(x, nd=8):
    return None if x is None else round(x, nd)


def code_revision(require_clean: bool = True) -> dict:
    """HEAD of the checkout this file runs from, and whether every file the run reads is tracked and unmodified."""
    def git(*args):
        return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, timeout=60)
    head = git("rev-parse", "HEAD")
    tracked = git("ls-files", "--error-unmatch", "--", *CODE_FILES)
    status = git("status", "--porcelain", "--untracked-files=no", "--", *CODE_FILES)
    clean = head.returncode == 0 and tracked.returncode == 0 and status.returncode == 0 and not status.stdout.strip()
    info = {"head": head.stdout.strip() if head.returncode == 0 else None, "clean": clean}
    if require_clean and not clean:
        raise Refused("code_not_committed")
    return info


# ----------------------------------------------------------------------------- sessions and requests

class Calendar:
    """XNYS sessions from mover-v3's pinned calendar (plan inputs.session_calendar), used for offsets only."""

    def __init__(self, days):
        self.days = list(days)
        self.index = {d: i for i, d in enumerate(self.days)}

    @classmethod
    def load(cls) -> "Calendar":
        raw = (ROOT / CALENDAR["path"]).read_bytes()
        if sha256_bytes(raw) != CALENDAR["sha256"]:
            raise Refused("calendar_sha256_mismatch")
        return cls(row[0] for row in json.loads(raw)["sessions"])

    def offset(self, day: str, n: int) -> str:
        if day not in self.index:
            raise ValueError("not a session")
        j = self.index[day] + n
        if not 0 <= j < len(self.days):
            raise ValueError("offset outside the calendar")
        return self.days[j]


def symbol_path(symbol: str) -> str:
    # audit.fetch_symbol quotes the symbol too (audit.py:308); safe="" keeps any symbol in one path segment.
    return "/v2/stocks/" + urllib.parse.quote(symbol, safe="")


def f1_specs(symbol, day, cal=None, *, asof=None, bars_start=None, bars_end=None, auctions_start=None) -> list:
    """requests.F1_event_leg: daily bars raw, split and all, then auctions, each with asof = the event date."""
    asof = asof or day
    bars_start = bars_start or cal.offset(day, -LOOKBACK)
    bars_end = bars_end or min(cal.offset(day, FORWARD), WINDOW[1])
    auctions_start = auctions_start or cal.offset(day, -AUCTION_LOOKBACK)
    path = symbol_path(symbol)
    specs = [{"leg": f"bars_{adj}", "path": path + "/bars",
              "params": {"timeframe": "1Day", "adjustment": adj, "asof": asof, "feed": "sip",
                         "start": bars_start, "end": bars_end, "limit": 10000}} for adj in ("raw", "split", "all")]
    specs.append({"leg": "auctions", "path": path + "/auctions",
                  "params": {"asof": asof, "feed": "sip", "start": auctions_start, "end": day}})
    return specs


def f2_spec(symbol, day, cal) -> dict:
    """requests.F2_today_symbol_leg: which issuer the frozen collection's symbol named on d."""
    return {"leg": F2_LEG, "path": symbol_path(symbol) + "/bars",
            "params": {"timeframe": "1Day", "adjustment": "raw", "asof": NAMING_ASOF, "feed": "sip",
                       "start": cal.offset(day, -1), "end": day}}


def control_specs(symbol) -> list:
    """requests.positive_control: the F1 bar and auction requests for session 2026-09-28."""
    return f1_specs(symbol, CONTROL_SESSION, asof=CONTROL_SESSION, bars_start=CONTROL_START,
                    bars_end=CONTROL_SESSION, auctions_start=CONTROL_START)


def overlaps_holdout(start: str, end: str) -> bool:
    return start <= HOLDOUT[1] and end >= HOLDOUT[0]


def check_holdout(specs) -> None:
    """guards.holdout: the whole request plan is checked before anything is sent; so is the market-data path."""
    for spec in specs:
        if not PRICE_PATH.fullmatch(spec["path"]):
            raise Refused("not_a_price_path")
        if overlaps_holdout(spec["params"]["start"], spec["params"]["end"]):
            raise Refused("holdout_window")


def control_time_ok(now=None) -> bool:
    """requests.positive_control: sent after 20:00 ET on 2026-09-28."""
    return (now or datetime.now(tz=ET)) >= CONTROL_NOT_BEFORE


class TextClient(audit.Client):
    """audit.Client (audit.py:260-296) with its pacing, 429 retries after 1, 2 and 4 s, 400/404/422 handling and
    page_token loop, and two changes. Each page body is kept as the provider's text, so labels parse the decimal
    text itself (plan labels.rule). A failure that audit.Client raises (429 after its retries, 5xx, a network
    error, the pagination guard, a body that is not JSON) is returned as an error record instead, because a
    failed request is an error, never no data (audit deviation D7)."""

    def get(self, path: str, **params) -> dict:
        pages, token, seen = [], None, set()
        while True:
            if token in seen or len(seen) > 1000:
                return {"error": "pagination_not_terminated"}
            if token:
                seen.add(token)
            q = dict(params, **({"page_token": token} if token else {}))
            url = audit.DATA_URL + path + "?" + urllib.parse.urlencode(q)
            for attempt in range(4):
                wait = self.last + self.gap - time.monotonic()
                if wait > 0:
                    time.sleep(wait)
                self.last = time.monotonic()
                try:
                    with urllib.request.urlopen(urllib.request.Request(url, headers=self.headers), timeout=30) as r:
                        raw = r.read()
                        self.log.append({"path": path, "params": q, "status": r.status})
                        break
                except urllib.error.HTTPError as exc:
                    self.log.append({"path": path, "params": q, "status": exc.code})
                    if exc.code == 429 and attempt < 3:
                        time.sleep(2 ** attempt)
                        continue
                    return {"error": exc.code}
                except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:
                    self.log.append({"path": path, "params": q, "status": f"network:{type(exc).__name__}"})
                    return {"error": f"network:{type(exc).__name__}"}
            try:
                text = raw.decode("utf-8")
                body = json.loads(text, parse_float=Decimal)
            except ValueError:
                return {"error": "invalid_json"}
            if not isinstance(body, dict):
                return {"error": "invalid_json"}
            pages.append(text)
            token = body.get("next_page_token")
            if not token:
                return {"pages": pages}


def fetch_legs(client, specs) -> dict:
    return {spec["leg"]: client.get(spec["path"], **spec["params"]) for spec in specs}


# ----------------------------------------------------------------------------- parsing

def leg_rows(leg, key: str):
    """('ok', rows) with each page's text parsed by json.loads(parse_float=Decimal); ('error', []) for a failed
    request and ('missing', []) for one never sent."""
    if not leg:
        return "missing", []
    if "error" in leg:
        return "error", []
    rows = []
    for text in leg["pages"]:
        rows.extend(json.loads(text, parse_float=Decimal).get(key) or [])
    return "ok", rows


def leg_key(leg: str) -> str:
    return "auctions" if leg == "auctions" else "bars"


def parse_legs(legs: dict, f2=None) -> tuple[dict, dict]:
    """(status by leg, rows by date by leg) for the four F1 legs and F2."""
    status, by = {}, {}
    for leg in F1_LEGS:
        status[leg], rows = leg_rows(legs.get(leg), leg_key(leg))
        by[leg] = audit.by_date(rows)
    status[F2_LEG], rows = leg_rows(f2, "bars")
    by[F2_LEG] = audit.by_date(rows)
    return status, by


def as_float(value):
    """The float view that the audit's functions expect (float(Decimal) rounds the decimal text once, as a JSON
    float parse would)."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {k: as_float(v) for k, v in value.items()}
    if isinstance(value, list):
        return [as_float(v) for v in value]
    return value


def dec(value) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(value)


def frac(value) -> Fraction:
    return Fraction(dec(value))


# ----------------------------------------------------------------------------- candidate rule and classes

_DERIVATIVE_FIVE = re.compile(r"[A-Z]{4}[WUR]$")
_DERIVATIVE_SUFFIX = re.compile(r"\.(WS|U|R|W)")


def derivative(symbol: str) -> bool:
    """candidates.py:47; DuckDB regexp_matches is a partial match, like re.search."""
    return bool((len(symbol) == 5 and _DERIVATIVE_FIVE.search(symbol)) or _DERIVATIVE_SUFFIX.search(symbol))


def touch(high, low) -> bool:
    """candidates.py:43, prev_l > 0 AND all_h >= 1.2 * prev_l, in IEEE-754 double: DuckDB casts the DECIMAL literal
    to DOUBLE for its product with the DOUBLE column."""
    high, low = float(high), float(low)
    return low > 0 and high >= TOUCH * low


def official_close_dec(day_auction, bar_close):
    """audit.official_close_v2 (audit.py:128-145), returning the print's own Decimal instead of a float."""
    if day_auction:
        closes = day_auction.get("c") or []
        listing = {o.get("x") for o in (day_auction.get("o") or []) if o.get("c") == "O"}
        on_listing = [c for c in closes if c.get("c") == "6" and c.get("x") in listing]
        if on_listing:
            return dec(max(on_listing, key=lambda c: c.get("s") or 0)["p"]), "closing_print_listing_exchange"
        official = [c for c in closes if c.get("c") == "M" and c.get("x") in listing]
        if official:
            return dec(official[0]["p"]), "official_close_listing_exchange"
        prints = [c for c in closes if c.get("c") == "6"]
        if prints:
            return dec(max(prints, key=lambda c: c.get("s") or 0)["p"]), "closing_print_other_exchange"
    if bar_close is not None:
        return dec(bar_close), "bar_close_fallback"
    return None, None


def official_close_checked(day_auction, bar):
    """The Decimal close, asserted equal to what audit.official_close_v2 selects from the float view."""
    price, source = official_close_dec(day_auction, bar["c"] if bar else None)
    want = audit.official_close_v2(as_float(day_auction), float(bar["c"]) if bar else None)
    if ((float(price) if price is not None else None), source) != want:
        raise AssertionError("the Decimal close selector disagrees with audit.official_close_v2")
    return price, source


def official_open_checked(day_auction):
    """sessions_io.official_price(day, "o") (the listing exchange's condition-O print, the largest by size), with
    the print's own Decimal, asserted equal to sessions_io's float answer."""
    opens = [o for o in ((day_auction or {}).get("o") or []) if o.get("c") == "O"]
    price, source = None, None
    if opens:
        top = max(opens, key=lambda o: (o.get("s") or 0, o.get("x") or ""))
        price, source = dec(top["p"]), "opening_print_listing_exchange"
    if ((float(price) if price is not None else None), source) != sessions_io.official_price(as_float(day_auction), "o"):
        raise AssertionError("the Decimal open selector disagrees with sessions_io.official_price")
    return price, source


def split_between(raw_d, split_d, status, day, prior):
    """tolerances.split_between with the audit's factor (audit.py:187-190) and v2 tolerance; None when a needed
    leg failed or a row is missing."""
    if status["bars_raw"] != "ok" or status["bars_split"] != "ok":
        return None
    f_day = audit.split_factor(as_float(raw_d.get(day)), as_float(split_d.get(day)))
    f_prior = audit.split_factor(as_float(raw_d.get(prior)), as_float(split_d.get(prior)))
    if not (f_day and f_prior):
        return None
    return abs(f_prior / f_day - 1) > audit.SPLIT_TOLERANCE["v2"]


def close_outside_bar(auc_d, raw_d, status, days):
    """An auction-sourced official close (audit v2 rule) of d or of the lag row outside that day's raw daily-bar
    low-high range (mover-early-entry deviations.json D3 remaining_gap); None when a needed leg failed."""
    if status["auctions"] != "ok" or status["bars_raw"] != "ok":
        return None
    for day in days:
        price, _ = official_close_dec(auc_d.get(day), None)
        bar = raw_d.get(day)
        if price is not None and bar is not None and not dec(bar["l"]) <= price <= dec(bar["h"]):
            return True
    return False


def identity(raw_d, f2_d, status, day) -> str:
    """tolerances.same_issuer: F1's and F2's raw o, h, l, c and v on d are all identical."""
    if status[F2_LEG] == "missing":
        return "f2_not_fetched"
    if status[F2_LEG] == "error":
        return "f2_error"
    if day not in f2_d:
        return "no_row"
    if status["bars_raw"] != "ok" or day not in raw_d:
        return "f1_raw_unavailable"
    a, b = raw_d[day], f2_d[day]
    same = all(k in a and k in b and a[k] == b[k] for k in ("o", "h", "l", "c", "v"))
    return "same_issuer" if same else "other_issuer"


def rename_on(renames, symbol, day) -> bool:
    return any(new == symbol and when == day for _, new, when in renames)


def successors(renames, symbol, day, until=NAMING_ASOF) -> set:
    """Symbols that name_change records chain `symbol` to, each hop dated after the previous one (the first after
    d) and none after `until`."""
    found, frontier, seen = set(), [(symbol, day)], set()
    while frontier:
        sym, after = frontier.pop()
        for old, new, when in renames:
            if old == sym and after < when <= until and (new, when) not in seen:
                seen.add((new, when))
                found.add(new)
                frontier.append((new, when))
    return found


def ratio_flags(num: Fraction, den: Fraction) -> dict:
    """labels.rule: Fraction(numerator) >= ratio x Fraction(denominator) (catalyst-experiment contract.py:126-128)."""
    return {name: num >= ratio * den for name, ratio in RATIOS}


def ratio_label(num, den, **extra) -> dict:
    if num is None or den is None or num <= 0 or den <= 0:
        return {"status": "undefined", "value": None, "flags": None, **extra}
    q = num / den - 1
    with localcontext() as ctx:  # display only (contract.py:120-124); the flags use exact rationals
        ctx.prec = 28
        value = str(Decimal(q.numerator) / Decimal(q.denominator))
    return {"status": "ok", "value": value, "flags": ratio_flags(num, den), **extra}


def undefined(status: str) -> dict:
    return {"status": status, "value": None, "flags": None}


def labels(day, raw_d, split_d, auc_d, gain, cal) -> dict:
    """labels.definitions on the Decimal rows. `gain` is audit.event_gain on their float view, which fixes the
    previous session and whether the split correction applies, exactly as the price audit decides them."""
    out = {"entry_to_exit": undefined("not_computed")}
    ev_bar = raw_d.get(day)
    if "reason" in gain:
        out["close_to_close_1d"] = out["prior_close_to_high_1d"] = undefined(gain["reason"])
    else:
        prev = gain["prev_date"]
        ev_close, ev_src = official_close_checked(auc_d.get(day), ev_bar)
        prev_close, prev_src = official_close_checked(auc_d.get(prev), raw_d.get(prev))
        if (ev_src, prev_src) != (gain["event_close_source"], gain["prev_close_source"]):
            raise AssertionError("the label closes are not the ones audit.event_gain used")
        f_ev = f_prev = Fraction(1)
        if gain["split_between"]:
            f_ev = frac(raw_d[day]["c"]) / frac(split_d[day]["c"])
            f_prev = frac(raw_d[prev]["c"]) / frac(split_d[prev]["c"])
        # (close_d / f_d) / (close_prev / f_prev), as audit.event_gain (audit.py:175-179)
        out["close_to_close_1d"] = ratio_label(frac(ev_close) * f_prev, frac(prev_close) * f_ev)
        out["prior_close_to_high_1d"] = (ratio_label(frac(ev_bar["h"]) * f_prev, frac(prev_close) * f_ev)
                                         if ev_bar else undefined("no_event_bar"))
    if ev_bar:
        opening, open_src = official_open_checked(auc_d.get(day))
        if opening is None:
            opening, open_src = dec(ev_bar["o"]), "bar_open_fallback"
        out["open_to_high_1d"] = ratio_label(frac(ev_bar["h"]), frac(opening), open_source=open_src)
    else:
        out["open_to_high_1d"] = undefined("no_event_bar")
    try:
        day5 = cal.offset(day, FORWARD)
    except ValueError:
        day5 = None
    if day5 is None:
        out["close_to_close_5d"] = undefined("censored_not_a_session")
    elif day5 > WINDOW[1]:
        out["close_to_close_5d"] = undefined("censored_after_window")
    elif day not in split_d or day5 not in split_d:
        out["close_to_close_5d"] = undefined("censored_no_bar")
    else:
        out["close_to_close_5d"] = ratio_label(frac(split_d[day5]["c"]), frac(split_d[day]["c"]))
    return out


def new_vintage_gain(day, status, by) -> dict:
    """audit.event_gain (rules v2) on the float view of one symbol's legs, computed only when the raw, split and
    auction legs all succeeded; otherwise undefined with reason leg_error. assess() and classify_e2() both use it,
    so E1 and E2 apply the same leg check before a gain counts."""
    if any(status[k] != "ok" for k in GAIN_LEGS):
        return {"reason": "leg_error"}
    return audit.event_gain(day, as_float(by["auctions"]), as_float(by["bars_raw"]), as_float(by["bars_split"]), "v2")


def assess(symbol, day, legs, f2, cal, renames=None, candidate_keys=None) -> dict:
    """The frozen candidate rule, reason classes (reason_classes.order), flags and labels for one symbol-day."""
    status, by = parse_legs(legs, f2)
    all_d, raw_d, split_d, auc_d, f2_d = (by[k] for k in ("bars_all", "bars_raw", "bars_split", "auctions", F2_LEG))
    gain = new_vintage_gain(day, status, by)
    lag = touched = None
    if status["bars_all"] == "ok" and day in all_d:
        earlier = [d for d in all_d if d < day]
        if earlier:
            lag = max(earlier)
            touched = touch(all_d[day]["h"], all_d[lag]["l"])
    failure = recovered = None
    if status["bars_all"] != "ok":
        failure = "fetch_error"
    elif day not in all_d:
        failure = "no_asof_event_row"
    elif derivative(symbol):
        failure = "derivative_pattern"
    elif lag is None:
        failure = "no_prior_row"
    elif not touched:
        if split_between(raw_d, split_d, status, day, lag):
            failure = "below_touch_split_basis"
        elif close_outside_bar(auc_d, raw_d, status, (day, lag)):
            failure = "below_touch_auction_outside_bar_range"
        else:
            failure = "below_touch_other"
    ident = identity(raw_d, f2_d, status, day)
    if failure is None:
        if renames is not None and rename_on(renames, symbol, day):
            recovered = "recovered_rename_on_event_date"
        elif (renames is not None and candidate_keys is not None
              and any((s, day) in candidate_keys for s in successors(renames, symbol, day))):
            recovered = "recovered_keyed_under_successor"
        else:
            recovered = {"other_issuer": "recovered_today_symbol_other_issuer",
                         "no_row": "recovered_today_symbol_no_row",
                         "same_issuer": "recovered_today_symbol_same_issuer"}.get(ident, "recovered_cause_unexplained")
    new_gain = gain.get("gain_pct")
    flags = {"leg_error": any(status[k] == "error" for k in ("bars_raw", "bars_split", "auctions", F2_LEG)),
             "otc_as_known": (None if status["auctions"] != "ok"
                              else not any(o.get("c") == "O" for o in (auc_d.get(day) or {}).get("o") or [])),
             "basis_uncertain": bool(gain.get("split_between"))
             or "bar_close_fallback" in (gain.get("event_close_source"), gain.get("prev_close_source")),
             "not_verified_in_new_vintage": new_gain is None or new_gain < MIN_GAIN_PCT,
             "prior_row_not_previous_session": None, "gap_over_7_days": None}
    if lag is not None:
        try:
            flags["prior_row_not_previous_session"] = lag != cal.offset(day, -1)
        except ValueError:
            flags["prior_row_not_previous_session"] = None
        flags["gap_over_7_days"] = (date.fromisoformat(day) - date.fromisoformat(lag)).days > 7
    return {"symbol": symbol, "day": day, "leg_status": status, "lag": lag, "touch": touched,
            "failure_class": failure, "recovered_class": recovered, "identity": ident, "flags": flags,
            "gain": {k: gain.get(k) for k in ("gain_pct", "prev_date", "event_close_source", "prev_close_source",
                                              "split_between", "reason")},
            "labels": labels(day, raw_d, split_d, auc_d, gain, cal)}


def event_class(result: dict, role: str):
    """reason_classes.rule: every missed event, and every control event that fails, gets exactly one class."""
    if result["failure_class"]:
        return result["failure_class"]
    return result["recovered_class"] if role == "missed" else None


def has_event_data(legs: dict, day: str) -> bool:
    """audit.has_event_data (audit.py:299-300): a raw bar or an auction record on the event date."""
    return any(day in audit.by_date(leg_rows(legs.get(leg), leg_key(leg))[1]) for leg in ("bars_raw", "auctions"))


# ----------------------------------------------------------------------------- renames

def name_changes(ca_dir) -> list:
    """(old_symbol, new_symbol, process_date) from corporate_actions.py pages (pages/<year>/pNNNN.json.gz)."""
    found = set()
    for path in sorted(Path(ca_dir).glob("pages/*/*.json.gz")):
        with gzip.open(path, "rb") as handle:
            body = json.loads(handle.read())
        actions = body.get("corporate_actions") or {}
        for kind in NAME_CHANGE_KINDS:
            for item in actions.get(kind) or ():
                old, new, when = item.get("old_symbol"), item.get("new_symbol"), item.get("process_date")
                if old and new and when and old != new:
                    found.add((old, new, when))
    return sorted(found)


def renames_complete(ca_dir):
    """broad-universe coverage.py check_corporate_actions_complete (coverage.py:180-212), restated because
    coverage.py imports duckdb: every planned year complete and a final run_complete with zero failures."""
    ca_dir = Path(ca_dir)
    plan_path, ledger_path = ca_dir / "plan.json", ca_dir / "ledger.jsonl"
    if not plan_path.exists():
        return False, ["missing plan.json"]
    if not ledger_path.exists():
        return False, ["missing ledger.jsonl"]
    plan = json.loads(plan_path.read_text())
    events = [json.loads(line) for line in ledger_path.read_text().splitlines() if line.strip()]
    types_key = plan.get("types_key")
    done = {e["year"] for e in events if e.get("event") == "year_complete" and e.get("types_key") == types_key}
    try:
        first, last = int(str(plan["start"])[:4]), int(str(plan["end"])[:4])
    except (KeyError, ValueError):
        return False, ["corporate-actions plan.json lacks a parsable start/end window"]
    reasons = [f"missing year_complete year={y} types_key={types_key}" for y in range(first, last + 1) if y not in done]
    runs = [e for e in events if e.get("event") == "run_complete" and e.get("types_key") == types_key]
    if not runs:
        reasons.append(f"no run_complete event for types_key={types_key}")
    elif runs[-1].get("failed", 1) != 0:
        reasons.append(f"latest run_complete reports failed={runs[-1].get('failed')}")
    return not reasons, reasons


def run_corporate_actions(env_file, ca_dir: Path, log_path: Path) -> int:
    """requests.renames through the repository's collector, as a child process (corporate_actions.py:316-325)."""
    cmd = [sys.executable, str(US / "broad-universe" / "corporate_actions.py"), "collect", "--env-file", str(env_file),
           "--out", str(ca_dir), "--start", RENAME_RANGE[0], "--end", RENAME_RANGE[1]]
    fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as log:
        return subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, timeout=3600).returncode


# ----------------------------------------------------------------------------- gate (E1, no network)

def read_keys(path) -> set:
    with Path(path).open(newline="") as handle:
        return {(r["symbol"], r["session_date"]) for r in csv.DictReader(handle)}


def locate_inputs(inputs: Path) -> dict:
    """The candidate files by the plan's names; the audit results by sha256 (plan inputs.location)."""
    found = {}
    for key in ("candidates_main", "candidates_premarket"):
        path = inputs / PLAN["inputs"][key]["file"]
        if path.is_file():
            found[key] = path
    want = PLAN["inputs"]["audit_results"]["sha256"]
    if inputs.is_dir():
        for path in sorted(inputs.iterdir()):
            if path.is_file() and path.suffix == ".json" and sha256_file(path) == want:
                found["audit_results"] = path
                break
    return found


def load_candidate_keys(inputs: Path) -> set:
    found = locate_inputs(inputs)
    keys = set()
    for key in ("candidates_main", "candidates_premarket"):
        if key not in found or sha256_file(found[key]) != PLAN["inputs"][key]["sha256"]:
            raise Refused("candidate_file_changed", file=key)
        keys |= read_keys(found[key])
    return keys


def split_events(audit_doc, main_keys, premarket_keys, tier, lo=WINDOW[0], hi=WINDOW[1]):
    """The missed and control events, with coverage()'s own filter and key test (evaluate.py:627-634)."""
    missed, controls = [], []
    for e in audit_doc["events"]:
        if e["verdict"] not in ("match", "recovered_match") or e.get("alpaca_gain_pct") is None:
            continue
        if e["alpaca_gain_pct"] < 20 or not (lo <= e["date"] <= hi):
            continue
        keys = {(e.get("symbol_used"), e["date"]), (e.get("ticker"), e["date"])}
        in_main, in_pre = bool(keys & main_keys), bool(keys & premarket_keys)
        row = {"id": e["id"], "date": e["date"], "ticker": e.get("ticker"), "symbol_used": e.get("symbol_used"),
               "symbol": e.get("symbol_used") or e.get("ticker"), "audit_gain_pct": e["alpaca_gain_pct"],
               "tier": tier(e["alpaca_gain_pct"] / 100)}
        if in_main or in_pre:
            held = "both" if in_main and in_pre else "main" if in_main else "premarket"
            controls.append(dict(row, role="control", held_by=held))
        else:
            missed.append(dict(row, role="missed", held_by=None))
    return missed, controls


def gate(args) -> int:
    out = private_dir(args.out_dir)
    doc = {"kind": "mover_coverage_asof_gate", "plan_sha256": PLAN_SHA256, "requests_sent": 0}
    try:
        plan_guard()
        found = locate_inputs(Path(args.inputs))
        want = {k: PLAN["inputs"][k]["sha256"] for k in INPUT_KEYS}
        missing = {k: want[k] for k in INPUT_KEYS if k not in found}
        if missing:
            raise Refused("inputs_missing", missing=missing)
        wrong = sorted(k for k in INPUT_KEYS if sha256_file(found[k]) != want[k])
        if wrong:
            raise Refused("input_sha256_mismatch", mismatched=wrong)
        evaluate, rules = mover_modules()
        cov = evaluate.coverage(found["audit_results"], [found["candidates_main"], found["candidates_premarket"]], *WINDOW)
        expected = PLAN["reproduction_gate"]["expected"]
        if cov != expected or cov != read_doc(COMMITTED_SUMMARY)["coverage"]:
            raise Refused("coverage_not_reproduced", coverage=cov)
        missed, controls = split_events(read_doc(found["audit_results"]), read_keys(found["candidates_main"]),
                                         read_keys(found["candidates_premarket"]), rules.degree_tier)
        if (len(missed), len(controls)) != (expected["events"] - expected["present"], expected["present"]):
            raise Refused("event_split_mismatch", missed=len(missed), controls=len(controls))
        plan_guard()
        events_sha = write_doc(out / "missed-events.json", {"kind": "mover_coverage_asof_events",
                                                            "plan_sha256": PLAN_SHA256, "events": missed + controls})
        doc.update(status="passed", coverage=cov, missed=len(missed), controls=len(controls), inputs_sha256=want,
                   controls_held_by=dict(sorted(Counter(e["held_by"] for e in controls).items())),
                   events_sha256=events_sha)
    except Refused as r:
        doc.update(status="refused", reason=r.reason, **r.detail)
    write_doc(out / "gate.json", doc)
    shown = {"reason": doc["reason"]} if doc["status"] != "passed" else {"missed": doc["missed"], "controls": doc["controls"]}
    print(json.dumps({"gate": doc["status"], **shown}))
    return 0 if doc["status"] == "passed" else 2


# ----------------------------------------------------------------------------- fetch (E1) and e2

def write_snapshots(out: Path, estimand, head_extra, f1, f2, ctrl, client) -> dict:
    head = {"plan_sha256": PLAN_SHA256, "estimand": estimand, **head_extra, "finished_at_utc": utc_now()}
    plan_guard()
    shas = {"snapshot-f1.json": write_doc(out / "snapshot-f1.json", dict(head, kind="mover_coverage_asof_f1", events=f1)),
            "snapshot-f2.json": write_doc(out / "snapshot-f2.json", dict(head, kind="mover_coverage_asof_f2", events=f2)),
            "control.json": write_doc(out / "control.json", dict(head, kind="mover_coverage_asof_control", symbols=ctrl))}
    counts = dict(sorted(Counter(str(e["status"]) for e in client.log).items()))
    shas["request-log.json"] = write_doc(out / "request-log.json", dict(
        head, kind="mover_coverage_asof_request_log", requests=len(client.log), status_counts=counts, log=client.log))
    status = dict(head, kind="mover_coverage_asof_fetch", status="complete", requests=len(client.log),
                  status_counts=counts, sha256=shas)
    write_doc(out / "fetch-status.json", status)
    print(json.dumps({"fetch": "complete", "estimand": estimand, "requests": len(client.log), "status_counts": counts}))
    return status


def fetch_control(client, head: dict) -> dict:
    specs = {sym: control_specs(sym) for sym in CONTROL_SYMBOLS}
    head["control_sent_at_utc"] = utc_now()
    return {sym: {"legs": fetch_legs(client, s)} for sym, s in specs.items()}


def run_e1_fetch(events, client, cal, out, fetched_at=None, code=None) -> dict:
    """F1 and F2 for the gate's events, after the whole request plan passes the holdout guard."""
    out = private_dir(out)
    plans = {}
    for ev in events:
        try:
            plans[ev["id"]] = (f1_specs(ev["symbol"], ev["date"], cal), f2_spec(ev["symbol"], ev["date"], cal))
        except ValueError:
            plans[ev["id"]] = None
    check_holdout([s for p in plans.values() if p for s in p[0] + [p[1]]]
                  + [s for sym in CONTROL_SYMBOLS for s in control_specs(sym)])
    head = {"fetched_at_utc": fetched_at or utc_now(), "code_revision": code}
    ctrl = fetch_control(client, head)
    f1, f2 = {}, {}
    for n, ev in enumerate(events, 1):
        plan = plans[ev["id"]]
        base = {"symbol": ev["symbol"], "day": ev["date"]}
        if plan is None:
            f1[ev["id"]] = dict(base, legs={leg: {"error": "not_a_session"} for leg in F1_LEGS})
            f2[ev["id"]] = dict(base, leg={"error": "not_a_session"})
            continue
        f1[ev["id"]] = dict(base, legs=fetch_legs(client, plan[0]))
        f2[ev["id"]] = dict(base, leg=client.get(plan[1]["path"], **plan[1]["params"]))
        if n % 100 == 0:
            print(json.dumps({"progress": n, "of": len(events), "requests": len(client.log)}), flush=True)
    return write_snapshots(out, "E1", head, f1, f2, ctrl, client)


def run_e2(events, client, cal, out, fetched_at=None, code=None) -> dict:
    """estimands.E2_rederived: symbols in audit load_events order until one has event-date data (audit.py:351-362),
    then F2 for that symbol."""
    out = private_dir(out)
    events = [e for e in events if WINDOW[0] <= e["date"] <= WINDOW[1]]
    plans = {}
    for ev in events:
        try:
            plans[ev["id"]] = [(s, f1_specs(s, ev["date"], cal), f2_spec(s, ev["date"], cal)) for s in ev["symbols"]]
        except ValueError:
            plans[ev["id"]] = None
    check_holdout([s for p in plans.values() if p for _, f1s, f2s in p for s in f1s + [f2s]]
                  + [s for sym in CONTROL_SYMBOLS for s in control_specs(sym)])
    head = {"fetched_at_utc": fetched_at or utc_now(), "code_revision": code}
    ctrl = fetch_control(client, head)
    f1, f2 = {}, {}
    for n, ev in enumerate(events, 1):
        plan = plans[ev["id"]]
        f2[ev["id"]] = None
        if plan is None:
            f1[ev["id"]] = {"day": ev["date"], "tried": [{"symbol": ev["symbols"][0],
                                                          "legs": {leg: {"error": "not_a_session"} for leg in F1_LEGS}}]}
            continue
        tried = []
        for sym, f1s, f2s in plan:
            got = fetch_legs(client, f1s)
            tried.append({"symbol": sym, "legs": got})
            if has_event_data(got, ev["date"]):
                f2[ev["id"]] = {"symbol": sym, "leg": client.get(f2s["path"], **f2s["params"])}
                break
        f1[ev["id"]] = {"day": ev["date"], "tried": tried}
        if n % 100 == 0:
            print(json.dumps({"progress": n, "of": len(events), "requests": len(client.log)}), flush=True)
    return write_snapshots(out, "E2", head, f1, f2, ctrl, client)


def refuse_fetch(out: Path, estimand: str, r: Refused, requests_sent: int = 0) -> int:
    doc = {"kind": "mover_coverage_asof_fetch", "estimand": estimand, "plan_sha256": PLAN_SHA256,
           "status": "refused", "reason": r.reason, "requests_sent": requests_sent, **r.detail}
    write_doc(out / "fetch-status.json", doc)
    print(json.dumps({"fetch": "refused", "estimand": estimand, "reason": r.reason}))
    return 2


def fetch(args) -> int:
    out = private_dir(args.out_dir)
    client = None
    try:
        plan_guard()
        code = code_revision()
        gate_doc = read_doc(out / "gate.json")
        if gate_doc.get("status") != "passed" or gate_doc.get("plan_sha256") != PLAN_SHA256:
            raise Refused("gate_not_passed")
        if sha256_file(out / "missed-events.json") != gate_doc["events_sha256"]:
            raise Refused("event_list_changed")
        events = read_doc(out / "missed-events.json")["events"]
        cal = Calendar.load()
        if not control_time_ok():
            raise Refused("control_before_2000_et")
        key, secret = audit.credentials(Path(args.env_file))  # 0600, owned; only the two key variables are read
        # renames first: a refusal there (collect_daily.py:35 accepts alphanumeric values only) stops the run
        # before any price request
        ca_dir = out / "corporate-actions"
        rc = run_corporate_actions(args.env_file, ca_dir, out / "corporate-actions.log")
        complete, reasons = renames_complete(ca_dir)
        if rc != 0 or not complete:
            raise Refused("renames_incomplete", exit_code=rc, reasons=reasons)
        client = TextClient(key, secret)
        del key, secret
        run_e1_fetch(events, client, cal, out, code=code)
    except Refused as r:
        return refuse_fetch(out, "E1", r, len(client.log) if client else 0)
    return 0


def extract_package(zip_path, dest) -> Path:
    """Only the two CSVs audit.load_events reads, byte for byte, to fixed names (no member path is trusted)."""
    dest = private_dir(dest)
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        for rel in (audit.FORWARD_CSV, audit.ALIAS_CSV):
            members = [n for n in names if n == rel or n.endswith("/" + rel)]
            if len(members) != 1:
                raise Refused("package_layout", file=rel)
            target = dest / rel
            private_dir(target.parent)
            write_private_bytes(target, zf.read(members[0]))
    return dest


def load_package_events(package_dir: Path) -> list:
    """audit.load_events (audit.py:69-89) after audit.check_inputs (audit.py:60-66), dated inside the window."""
    try:
        audit.check_inputs(package_dir)
    except SystemExit as exc:
        raise Refused("package_csv_sha256_mismatch") from exc
    return [e for e in audit.load_events(package_dir) if WINDOW[0] <= e["date"] <= WINDOW[1]]


def e2_cmd(args) -> int:
    out = private_dir(args.out_dir)
    client = None
    try:
        plan_guard()
        code = code_revision()
        if sha256_file(args.package_zip) != PLAN["inputs"]["package_zip"]["sha256"]:
            raise Refused("package_sha256_mismatch")
        events = load_package_events(extract_package(args.package_zip, out / "inputs" / "package"))
        cal = Calendar.load()
        if not control_time_ok():
            raise Refused("control_before_2000_et")
        key, secret = audit.credentials(Path(args.env_file))  # 0600, owned; only the two key variables are read
        client = TextClient(key, secret)
        del key, secret
        run_e2(events, client, cal, out, code=code)
    except Refused as r:
        return refuse_fetch(out, "E2", r, len(client.log) if client else 0)
    return 0


# ----------------------------------------------------------------------------- classify (no network)

def zero_counts(keys, values) -> dict:
    c = Counter(values)
    return {k: c.get(k, 0) for k in keys}


def flag_totals(rows) -> dict:
    out = {}
    for name in FLAG_NAMES:
        values = [r["flags"][name] for r in rows if r.get("flags")]
        out[name] = {"true": sum(v is True for v in values), "false": sum(v is False for v in values),
                     "unknown": sum(v is None for v in values)}
    return out


def c2c_flag(label_doc, rid, ratio) -> bool:
    flags = ((label_doc.get(rid) or {}).get("close_to_close_1d") or {}).get("flags") or {}
    return bool(flags.get(ratio))


def exposure(f1doc, f2doc, ctrl) -> dict:
    """guards.exposure_record, counted on the rows the snapshots actually hold."""
    counts = {"price_rows_total": 0, "price_rows_before_2021_01_04": 0, "price_rows_in_holdout": 0}

    def add(leg, key):
        for row in leg_rows(leg, key)[1]:
            day = row.get("d") or str(row.get("t", ""))[:10]
            counts["price_rows_total"] += 1
            counts["price_rows_before_2021_01_04"] += day < WINDOW[0]
            counts["price_rows_in_holdout"] += HOLDOUT[0] <= day <= HOLDOUT[1]
    for ev in f1doc["events"].values():
        for t in ev.get("tried") or [ev]:
            for leg in F1_LEGS:
                add(t["legs"].get(leg), leg_key(leg))
    for ev in f2doc["events"].values():
        if ev:
            add(ev["leg"], "bars")
    for sym in ctrl["symbols"].values():
        for leg in F1_LEGS:
            add(sym["legs"].get(leg), leg_key(leg))
    return counts


def leg_outcomes(f1doc, f2doc, ctrl) -> dict:
    """requests.failures: empty responses and errors counted per leg, never dropped."""
    out, errors = {}, Counter()

    def add(group, leg, key):
        status, rows = leg_rows(leg, key)
        c = out.setdefault(group, {"ok_with_rows": 0, "ok_empty": 0, "error": 0})
        if status == "error":
            c["error"] += 1
            errors[str(leg["error"])] += 1
        elif status == "ok":
            c["ok_with_rows" if rows else "ok_empty"] += 1
    for ev in f1doc["events"].values():
        for t in ev.get("tried") or [ev]:
            for leg in F1_LEGS:
                add(f"f1_{leg}", t["legs"].get(leg), leg_key(leg))
    for ev in f2doc["events"].values():
        if ev:
            add("f2_bars_raw", ev["leg"], "bars")
    for sym in ctrl["symbols"].values():
        for leg in F1_LEGS:
            add(f"control_{leg}", sym["legs"].get(leg), leg_key(leg))
    return {"legs": dict(sorted(out.items())), "error_codes": dict(sorted(errors.items()))}


def run_facts(out: Path, f1doc, f2doc, ctrl, cal) -> dict:
    control = {sym: assess(sym, CONTROL_SESSION, ctrl["symbols"][sym]["legs"], None, cal)["touch"] is True
               for sym in CONTROL_SYMBOLS}
    positive = {sym: {"touch": passed} for sym, passed in control.items()}
    positive["passed"] = all(control.values())
    reqlog = read_doc(out / "request-log.json")
    return {"positive_control": positive, "exposure": exposure(f1doc, f2doc, ctrl),
            "requests": {"total": reqlog["requests"], "status_counts": reqlog["status_counts"]},
            "responses": leg_outcomes(f1doc, f2doc, ctrl),
            "snapshots_sha256": {n: sha256_file(out / n) for n in SNAPSHOT_FILES},
            "fetched_at_utc": f1doc.get("fetched_at_utc"), "control_sent_at_utc": f1doc.get("control_sent_at_utc"),
            "finished_at_utc": f1doc.get("finished_at_utc"), "code_revision": f1doc.get("code_revision")}


def vendor_agreement(new_gain, audit_gain) -> str:
    """tolerances.vendor_agreement, with the audit's own agrees() and event_gain tolerance."""
    if new_gain is None or new_gain < MIN_GAIN_PCT:
        return "not_verified_in_new_vintage"
    return "agree" if audit.agrees(new_gain, audit_gain, audit.PLAN["tolerance"]["event_gain"]) else "disagree"


def coverage_block(extra: int) -> dict:
    expected = PLAN["reproduction_gate"]["expected"]
    present = expected["present"] + extra
    return {"present": present, "events": expected["events"], "share": rnd(present / expected["events"]),
            "meets_95_percent": present * 100 >= 95 * expected["events"]}


def classify_e1(out: Path, inputs: Path, f1doc, f2doc, ctrl, cal, rules):
    gate_doc = read_doc(out / "gate.json")
    if gate_doc.get("status") != "passed" or sha256_file(out / "missed-events.json") != gate_doc.get("events_sha256"):
        raise Refused("gate_not_passed")
    events = read_doc(out / "missed-events.json")["events"]
    candidate_keys = load_candidate_keys(inputs)
    renames = name_changes(out / "corporate-actions")
    results, label_doc = [], {}
    for ev in events:
        a = assess(ev["symbol"], ev["date"], f1doc["events"][ev["id"]]["legs"], f2doc["events"][ev["id"]]["leg"], cal,
                   renames=renames, candidate_keys=candidate_keys)
        results.append({**{k: ev[k] for k in ("id", "date", "ticker", "symbol", "role", "held_by", "tier",
                                              "audit_gain_pct")},
                        "class": event_class(a, ev["role"]), "touch": a["touch"], "identity": a["identity"],
                        "flags": a["flags"], "lag": a["lag"], "gain": a["gain"], "leg_status": a["leg_status"],
                        "vendor_agreement": vendor_agreement(a["gain"]["gain_pct"], ev["audit_gain_pct"])})
        label_doc[ev["id"]] = a["labels"]
    missed = [r for r in results if r["role"] == "missed"]
    controls = [r for r in results if r["role"] == "control"]
    recovered = [r for r in missed if (r["class"] or "").startswith("recovered_")]
    held = ("main", "premarket", "both")

    def control_block(rs):
        return {"events": len(rs), "touch_passes": sum(r["touch"] is True for r in rs),
                "failure_classes": zero_counts(CLASS_ORDER[:7], [r["class"] for r in rs if r["class"]])}

    def group(rs_missed, rs_controls):
        rec = [r for r in rs_missed if (r["class"] or "").startswith("recovered_")]
        return {"missed": len(rs_missed), "recovered": len(rec), "classes": zero_counts(CLASS_ORDER, [r["class"] for r in rs_missed]),
                "controls": len(rs_controls), "control_touch_passes": sum(r["touch"] is True for r in rs_controls)}
    tiers = [rules.tier_label(i) for i in range(len(rules.DEGREE_TIERS))]
    e1 = {"status": "run", "missed": len(missed), "controls": len(controls), "recovered": len(recovered),
          "recovered_needed_for_95_percent": 67,
          "coverage_with_asof": coverage_block(len(recovered)),
          "coverage_with_asof_without_otc_as_known": coverage_block(
              sum(1 for r in recovered if r["flags"]["otc_as_known"] is not True)),
          "coverage_frozen_rekeyed": coverage_block(sum(1 for r in missed if r["class"] == "recovered_keyed_under_successor")),
          "classes_of_missed": zero_counts(CLASS_ORDER, [r["class"] for r in missed]),
          "asof_recount": {"touch_passes_among_missed": sum(r["touch"] is True for r in missed),
                           "controls_by_candidate_file": {h: control_block([r for r in controls if r["held_by"] == h]) for h in held},
                           "control_f2_identity": zero_counts(IDENTITY_OUTCOMES, [r["identity"] for r in controls]),
                           "missed_f2_identity": zero_counts(IDENTITY_OUTCOMES, [r["identity"] for r in missed])},
          "by_tier": {t: group([r for r in missed if r["tier"] == t], [r for r in controls if r["tier"] == t]) for t in tiers},
          "by_close_to_close_1d_ratio": {name: group([r for r in missed if c2c_flag(label_doc, r["id"], name)],
                                                     [r for r in controls if c2c_flag(label_doc, r["id"], name)])
                                         for name, _ in RATIOS},
          "flags": {"missed": flag_totals(missed), "controls": flag_totals(controls)},
          "vendor_agreement": {"missed": zero_counts(("agree", "disagree", "not_verified_in_new_vintage"), [r["vendor_agreement"] for r in missed]),
                               "controls": zero_counts(("agree", "disagree", "not_verified_in_new_vintage"), [r["vendor_agreement"] for r in controls])},
          "renames": {"name_change_records": len(renames)},
          "gate": {k: gate_doc[k] for k in ("coverage", "missed", "controls", "controls_held_by")}}
    return results, label_doc, {"E1": e1}


def e2_source(day, tried) -> tuple:
    """audit compare's walk over the tried symbols (audit.py:406-411), with new_vintage_gain as each symbol's gain:
    the first symbol whose gain is defined, or lacks only a previous close, is used. A symbol with a failed raw,
    split or auction leg ends the walk with no symbol used. Its gain is unknown, and so is whether it held the
    event, because a failed request is never read as no data (audit deviation D7)."""
    for t in tried:
        status, by = parse_legs(t["legs"])
        gain = new_vintage_gain(day, status, by)
        if gain.get("reason") == "leg_error":
            return None, gain
        if "reason" not in gain or gain["reason"] == "no_prev_close":
            return t, gain
    return None, {"reason": "no_source_data"}


def classify_e2(out: Path, f1doc, f2doc, cal, rules):
    events = load_package_events(out / "inputs" / "package")
    rows, label_doc = [], {}
    for ev in events:
        snap = f1doc["events"].get(ev["id"])
        tried = snap["tried"] if snap else []
        used, gain = e2_source(ev["date"], tried)
        verdict = audit.verdict_for(ev, gain, "v2")[0] if snap else "not_fetched"
        if verdict == "leg_error":
            verdict = "fetch_error"  # audit deviation D7 (audit.py:413-414): a failed request, never no data
        in_n2 = (verdict in ("match", "recovered_match") and gain.get("gain_pct") is not None
                 and gain["gain_pct"] >= MIN_GAIN_PCT)
        f2 = f2doc["events"].get(ev["id"]) or {}
        f2_leg = f2.get("leg") if used and f2.get("symbol") == used["symbol"] else None
        a = assess(used["symbol"], ev["date"], used["legs"], f2_leg, cal) if used else None
        if in_n2 and a["gain"]["gain_pct"] != gain["gain_pct"]:
            raise AssertionError("an N2 event's gain is not the one assess() computed on the same legs")
        rows.append({"id": ev["id"], "date": ev["date"], "ticker": ev["ticker"],
                     "symbol_used": used["symbol"] if used else None, "verdict": verdict,
                     "gain_pct": gain.get("gain_pct"), "in_n2": in_n2,
                     "tier": rules.degree_tier(gain["gain_pct"] / 100) if in_n2 else None,
                     "touch": a["touch"] if a else None, "failure_class": a["failure_class"] if a else None,
                     "candidate_rule_pass": bool(a) and a["failure_class"] is None,
                     "identity": a["identity"] if a else None, "flags": a["flags"] if a else None,
                     "lag": a["lag"] if a else None, "leg_status": a["leg_status"] if a else None})
        if a:
            label_doc[ev["id"]] = a["labels"]
    n2 = [r for r in rows if r["in_n2"]]
    committed = PLAN["reproduction_gate"]["expected"]

    def block(rs):
        return {"N2": len(rs), "touch_passes": sum(r["touch"] is True for r in rs),
                "candidate_rule_passes": sum(r["candidate_rule_pass"] for r in rs),
                "f2_identity": zero_counts(IDENTITY_OUTCOMES, [r["identity"] for r in rs])}
    by_tier = {}
    for i in range(len(rules.DEGREE_TIERS)):
        t = rules.tier_label(i)
        c = committed["by_tier"][t]
        by_tier[t] = dict(block([r for r in n2 if r["tier"] == t]), committed_events=c["events"],
                          committed_missed=c["events"] - c["present"],
                          N2_minus_committed_events=sum(1 for r in n2 if r["tier"] == t) - c["events"])
    e2 = {"package_events_in_window": len(rows), "N2": len(n2),
          "N2_minus_committed_events": len(n2) - committed["events"],
          "touch_passes_among_N2": sum(r["touch"] is True for r in n2),
          "candidate_rule_passes_among_N2": sum(r["candidate_rule_pass"] for r in n2),
          "touch_share_among_N2": rnd(sum(r["touch"] is True for r in n2) / len(n2)) if n2 else None,
          "candidate_rule_share_among_N2": rnd(sum(r["candidate_rule_pass"] for r in n2) / len(n2)) if n2 else None,
          "f2_identity_among_N2": zero_counts(IDENTITY_OUTCOMES, [r["identity"] for r in n2]),
          # Post hoc, added after the first classify: the identity test's other-issuer side, on the package
          # events outside N2. It changes no estimand.
          "f2_identity_outside_N2_post_hoc": zero_counts(IDENTITY_OUTCOMES + ("no_event_data",),
                                                        [r["identity"] or "no_event_data" for r in rows if not r["in_n2"]]),
          "failure_classes_among_N2": zero_counts(CLASS_ORDER[:7], [r["failure_class"] for r in n2 if r["failure_class"]]),
          "verdicts": dict(sorted(Counter(r["verdict"] for r in rows).items())),
          "flags_among_N2": flag_totals(n2), "by_tier": by_tier,
          "by_close_to_close_1d_ratio": {name: block([r for r in n2 if c2c_flag(label_doc, r["id"], name)])
                                         for name, _ in RATIOS},
          "committed_reference": {"events": committed["events"], "present": committed["present"],
                                  "missed_by_tier": {t: v["committed_missed"] for t, v in by_tier.items()}}}
    return rows, label_doc, {"E2": e2}


def classify_outputs(out: Path, inputs=None) -> tuple:
    """(estimand, {name: bytes}) for CLASSIFY_OUTPUTS, computed from the sealed snapshots alone. Nothing is
    written, so a retained run can be recomputed without touching it."""
    plan_guard()
    f1doc, f2doc, ctrl = (read_doc(out / n) for n in ("snapshot-f1.json", "snapshot-f2.json", "control.json"))
    if any(d.get("plan_sha256") != PLAN_SHA256 for d in (f1doc, f2doc, ctrl)):
        raise Refused("snapshot_under_another_plan")
    estimand = f1doc["estimand"]
    cal = Calendar.load()
    _, rules = mover_modules()
    if estimand == "E1":
        results, label_doc, body = classify_e1(out, Path(inputs) if inputs else out / "inputs",
                                               f1doc, f2doc, ctrl, cal, rules)
    else:
        results, label_doc, body = classify_e2(out, f1doc, f2doc, cal, rules)
    head = {"plan_sha256": PLAN_SHA256, "estimand": estimand}
    docs = {"results.json": dict(head, kind="mover_coverage_asof_results", events=results),
            "labels.json": dict(head, kind="mover_coverage_asof_labels", labels=label_doc),
            "summary.json": dict(head, kind="mover_coverage_asof_private_summary", **body,
                                 **run_facts(out, f1doc, f2doc, ctrl, cal))}
    return estimand, {name: dumps(doc) for name, doc in docs.items()}


def classify(args) -> int:
    out = Path(args.out_dir)
    estimand, blobs = classify_outputs(out, args.inputs)
    head = {"plan_sha256": PLAN_SHA256, "estimand": estimand}
    plan_guard()
    if args.verify:
        same = {name: (out / name).exists() and (out / name).read_bytes() == blob for name, blob in blobs.items()}
        # The revision lives here, not in the classify outputs, which depend on the sealed snapshots alone
        # (plan outputs.determinism), so a verify at a later commit can still compare them byte for byte.
        verify = dict(head, kind="mover_coverage_asof_verify", byte_identical=all(same.values()),
                      sha256={name: sha256_bytes(blob) for name, blob in blobs.items()},
                      classify_code_revision=code_revision(require_clean=False))
        write_doc(out / "verify.json", verify)
        print(json.dumps({"verify": estimand, "byte_identical": verify["byte_identical"]}))
        return 0 if verify["byte_identical"] else 3
    shas = {name: write_private_bytes(out / name, blob) for name, blob in blobs.items()}
    print(json.dumps({"classify": estimand, "sha256": shas}))
    return 0


# ----------------------------------------------------------------------------- publish (totals only)

PATHLIKE = re.compile(r"(/home/|/tmp/|/mnt/|/run/user|/var/|\.local/|~/)")
DATELIKE = re.compile(r"\d{4}-\d{2}-\d{2}")
SYMBOLLIKE = re.compile(r"[A-Z]{1,5}(\.[A-Z]{1,2})?")

# guards.publication as an explicit schema of the committed summary. Every key is named here or drawn from the
# runner's own vocabularies (tiers, ratios, classes, flags, identity outcomes, verdicts, leg groups, request status
# codes and lowercase private file names). Every leaf is a count, a share in [0, 1], a boolean, a sha256, a git
# revision, a fetch timestamp or a short text. None stands for an absent value anywhere.
TIER_LABELS = tuple(PLAN["reproduction_gate"]["expected"]["by_tier"])
RATIO_NAMES = tuple(name for name, _ in RATIOS)
VERDICTS = ("fetch_error", "match", "mismatch", "no_package_reference", "no_prev_close", "no_source_data", "not_fetched",
            "package_uncomputed_match", "package_uncomputed_mismatch", "recovered_match", "recovered_mismatch")
HELD_BY = ("main", "premarket", "both")
AGREEMENT = ("agree", "disagree", "not_verified_in_new_vintage")
LEG_GROUPS = tuple(f"f1_{leg}" for leg in F1_LEGS) + (F2_LEG,) + tuple(f"control_{leg}" for leg in F1_LEGS)
STATUS_KEY = re.compile(r"\d{3}|network:[A-Za-z]+|pagination_not_terminated|invalid_json|not_a_session")
PRIVATE_FILE_KEY = re.compile(r"[a-z0-9][a-z0-9._-]*(/[a-z0-9][a-z0-9._-]*)*")
LEAVES = {
    "int": ("an integer", lambda v: isinstance(v, int) and not isinstance(v, bool)),
    "share": ("a share", lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 1),
    "bool": ("a boolean", lambda v: isinstance(v, bool)),
    "text": ("text", lambda v: isinstance(v, str)),
    "sha256": ("a sha256", lambda v: isinstance(v, str) and re.fullmatch(r"[0-9a-f]{64}", v) is not None),
    "revision": ("a revision", lambda v: isinstance(v, str) and re.fullmatch(r"[0-9a-f]{40}", v) is not None),
    "timestamp": ("a timestamp", lambda v: isinstance(v, str)
                  and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", v) is not None),
}


class Keys:
    """A schema map whose keys fullmatch `pattern` and whose values all follow `value`."""

    def __init__(self, pattern, value):
        self.pattern, self.value = pattern, value


def counts(names) -> dict:
    return dict.fromkeys(names, "int")


def public_schema() -> dict:
    """The E1 and E2 blocks as estimand_block and publish write them: classify_e1's or classify_e2's totals, the
    run facts, validity and private file hashes; E1 also as the gate-only block of a run that was not classified."""
    identity, flags = counts(IDENTITY_OUTCOMES), {name: counts(("true", "false", "unknown")) for name in FLAG_NAMES}
    share = {"present": "int", "events": "int", "share": "share", "meets_95_percent": "bool"}
    group = {"missed": "int", "recovered": "int", "classes": counts(CLASS_ORDER), "controls": "int",
             "control_touch_passes": "int"}
    n2 = {"N2": "int", "touch_passes": "int", "candidate_rule_passes": "int", "f2_identity": identity}
    common = {"status": "text",
              "positive_control": {**{s: {"touch": "bool"} for s in CONTROL_SYMBOLS}, "passed": "bool"},
              "exposure": counts(("price_rows_total", "price_rows_before_2021_01_04", "price_rows_in_holdout")),
              "requests": {"total": "int", "status_counts": Keys(STATUS_KEY, "int")},
              "responses": {"legs": {g: counts(("ok_with_rows", "ok_empty", "error")) for g in LEG_GROUPS},
                            "error_codes": Keys(STATUS_KEY, "int")},
              **dict.fromkeys(TIMESTAMP_KEYS, "timestamp"),
              "code_revision": {"head": "revision", "clean": "bool"},
              "classify_code_revision": {"head": "revision", "clean": "bool"},
              "validity": {**dict.fromkeys(("positive_control_passed", "classify_rerun_byte_identical",
                                            "no_holdout_rows", "gate_reproduced", "stands"), "bool"), "label": "text"},
              "private_files_sha256": Keys(PRIVATE_FILE_KEY, "sha256")}
    e1 = {**common, "missed": "int", "controls": "int", "recovered": "int", "recovered_needed_for_95_percent": "int",
          "coverage_with_asof": share, "coverage_with_asof_without_otc_as_known": share,
          "coverage_frozen_rekeyed": share, "classes_of_missed": counts(CLASS_ORDER),
          "asof_recount": {"touch_passes_among_missed": "int",
                           "controls_by_candidate_file": {h: {"events": "int", "touch_passes": "int",
                                                              "failure_classes": counts(CLASS_ORDER[:7])}
                                                          for h in HELD_BY},
                           "control_f2_identity": identity, "missed_f2_identity": identity},
          "by_tier": dict.fromkeys(TIER_LABELS, group), "by_close_to_close_1d_ratio": dict.fromkeys(RATIO_NAMES, group),
          "flags": {"missed": flags, "controls": flags},
          "vendor_agreement": {"missed": counts(AGREEMENT), "controls": counts(AGREEMENT)},
          "renames": {"name_change_records": "int"},
          "gate": {"coverage": {"events": "int", "present": "int", "share": "share", "survivorship_limited": "bool",
                                "by_tier": dict.fromkeys(TIER_LABELS, {"events": "int", "present": "int"})},
                   "missed": "int", "controls": "int", "controls_held_by": counts(HELD_BY), "status": "text",
                   "reason": "text", "requests_sent": "int", "missing_inputs_sha256": dict.fromkeys(INPUT_KEYS, "sha256")}}
    e2 = {**common, "package_events_in_window": "int", "N2": "int", "N2_minus_committed_events": "int",
          "touch_passes_among_N2": "int", "candidate_rule_passes_among_N2": "int", "touch_share_among_N2": "share",
          "candidate_rule_share_among_N2": "share", "f2_identity_among_N2": identity,
          "f2_identity_outside_N2_post_hoc": counts(IDENTITY_OUTCOMES + ("no_event_data",)),
          "failure_classes_among_N2": counts(CLASS_ORDER[:7]), "verdicts": counts(VERDICTS), "flags_among_N2": flags,
          "by_tier": dict.fromkeys(TIER_LABELS, {**n2, "committed_events": "int", "committed_missed": "int",
                                                 "N2_minus_committed_events": "int"}),
          "by_close_to_close_1d_ratio": dict.fromkeys(RATIO_NAMES, n2),
          "committed_reference": {"events": "int", "present": "int", "missed_by_tier": counts(TIER_LABELS)}}
    return {"kind": "text", "schema_version": "int", "privacy": "text",
            "plan": {"path": "text", "sha256": "sha256", "bytes": "int"}, "E1": e1, "E2": e2}


PUBLIC_SCHEMA = public_schema()


def schema_problems(node, schema, where="$") -> list:
    """Each key the schema does not name and each leaf of the wrong kind."""
    if node is None:
        return []
    if isinstance(schema, str):
        what, test = LEAVES[schema]
        return [] if test(node) else [f"{where}: expected {what}"]
    if not isinstance(node, dict):
        return [f"{where}: expected an object"]
    problems = []
    for key, value in node.items():
        if isinstance(schema, Keys):
            sub = schema.value if schema.pattern.fullmatch(str(key)) else None
        else:
            sub = schema.get(key)
        if sub is None:
            problems.append(f"{where}.{key}: unexpected key")
        else:
            problems += schema_problems(value, sub, f"{where}.{key}")
    return problems


def scan_public(doc, private_roots=()) -> list:
    """guards.publication, checked on the document itself: it follows PUBLIC_SCHEMA, so a key the schema does not
    name is refused; no key is symbol-like other than the named control; and no host path, no date outside a
    fetch timestamp, no symbol-like value, and no non-integer number other than a share in [0, 1] appears."""
    problems = schema_problems(doc, PUBLIC_SCHEMA)

    def walk(node, where):
        if isinstance(node, dict):
            for k, v in node.items():
                here = f"{where}.{k}"
                if DATELIKE.search(str(k)) or PATHLIKE.search(str(k)):
                    problems.append(f"{here}: date or path in key")
                if SYMBOLLIKE.fullmatch(str(k)) and k not in CONTROL_SYMBOLS:
                    problems.append(f"{here}: symbol-like key")
                walk(v, here)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{where}[{i}]")
        elif isinstance(node, str):
            if PATHLIKE.search(node) or any(root and root in node for root in private_roots):
                problems.append(f"{where}: path")
            if DATELIKE.search(node) and where.rsplit(".", 1)[-1] not in TIMESTAMP_KEYS:
                problems.append(f"{where}: date")
            if SYMBOLLIKE.fullmatch(node) and node not in CONTROL_SYMBOLS:
                problems.append(f"{where}: symbol-like value")
        elif isinstance(node, float) and not 0.0 <= node <= 1.0:
            problems.append(f"{where}: number that is not a share")
    walk(doc, "$")
    return problems


def private_files(folder: Path) -> dict:
    return {str(p.relative_to(folder)): sha256_file(p) for p in sorted(folder.rglob("*")) if p.is_file()}


def same_run(doc, kind: str, name: str) -> bool:
    """doc is a `kind` output of this plan (its sha256, the plan's identity) for estimand `name`."""
    return isinstance(doc, dict) and (doc.get("kind"), doc.get("plan_sha256"), doc.get("estimand")) == (
        kind, PLAN_SHA256, name)


def rerun_verified(folder: Path, name: str, summary: dict, verify) -> bool:
    """validity's "a second classify on the same snapshots is byte-identical", taken from verify.json only when it
    is this plan's verify for this estimand, found the rerun byte-identical and recorded the sha256 of the classify
    outputs now on disk, while summary.json names the snapshots now on disk. A stale or unrelated verify.json, or
    any classify output or snapshot changed after it, leaves the condition false."""
    if not same_run(verify, "mover_coverage_asof_verify", name) or verify.get("byte_identical") is not True:
        return False
    outputs, snapshots = verify.get("sha256"), summary.get("snapshots_sha256")
    if not (isinstance(outputs, dict) and sorted(outputs) == sorted(CLASSIFY_OUTPUTS)
            and isinstance(snapshots, dict) and sorted(snapshots) == sorted(SNAPSHOT_FILES)):
        return False
    return all((folder / n).is_file() and sha256_file(folder / n) == want
               for n, want in [*outputs.items(), *snapshots.items()])


def estimand_block(folder: Path, name: str, gate_ok: bool) -> dict:
    summary = read_doc(folder / "summary.json")
    if not same_run(summary, "mover_coverage_asof_private_summary", name):
        raise Refused("summary_not_this_plan_or_estimand", estimand=name)
    verify = read_doc(folder / "verify.json") if (folder / "verify.json").exists() else {}
    block = dict(summary[name])
    for key in ("positive_control", "exposure", "requests", "responses", "fetched_at_utc", "control_sent_at_utc",
                "finished_at_utc", "code_revision"):
        block[key] = summary.get(key)
    # the verify's revision is carried only from this plan's verify of this estimand
    block["classify_code_revision"] = (verify.get("classify_code_revision")
                                       if same_run(verify, "mover_coverage_asof_verify", name) else None)
    conditions = {"positive_control_passed": summary["positive_control"]["passed"],
                  "classify_rerun_byte_identical": rerun_verified(folder, name, summary, verify),
                  "no_holdout_rows": summary["exposure"]["price_rows_in_holdout"] == 0}
    if name == "E1":
        conditions["gate_reproduced"] = gate_ok
    block["validity"] = {**conditions, "stands": all(conditions.values()),
                         "label": None if conditions["positive_control_passed"] else "recipe_control_failed"}
    block["private_files_sha256"] = private_files(folder)
    return block


def publish(args) -> int:
    plan_guard()
    run = Path(args.run_dir)
    gate_doc = read_doc(run / "gate.json")
    doc = {"kind": "mover_coverage_asof_summary", "schema_version": 1,
           "plan": {"path": str(PLAN_PATH.relative_to(ROOT)), "sha256": PLAN_SHA256, "bytes": len(PLAN_BYTES)},
           "privacy": "Totals only (plan guards.publication). Event lists, symbols, dates, prices, label values and "
                      "per-event classes stay in the private trial workspace; each private file is named by sha256."}
    gate_ok = gate_doc.get("status") == "passed" and gate_doc.get("plan_sha256") == PLAN_SHA256
    if gate_ok and (run / "summary.json").exists():
        doc["E1"] = estimand_block(run, "E1", gate_ok)
    else:
        doc["E1"] = {"status": "not_run" if not gate_ok else "gate_passed_not_classified",
                     "coverage_with_asof": None,
                     "gate": {"status": gate_doc.get("status"), "reason": gate_doc.get("reason"),
                              "requests_sent": gate_doc.get("requests_sent"),
                              "missing_inputs_sha256": gate_doc.get("missing")}}
    if args.e2_dir:
        doc["E2"] = estimand_block(Path(args.e2_dir), "E2", gate_ok)
        doc["E2"]["status"] = "run"
    problems = scan_public(doc, private_roots=(str(run.resolve()), str(Path(args.e2_dir).resolve()) if args.e2_dir else "",
                                               str(Path.home())))
    if problems:
        print(json.dumps({"publish": "refused", "problems": problems}))
        return 3
    body = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    Path(args.to).write_text(body)
    print(json.dumps({"publish": "written", "sha256": sha256_bytes(body.encode())}))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gate")
    g.add_argument("--inputs", type=Path, required=True)
    g.add_argument("--out-dir", type=Path, required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--env-file", type=Path, required=True)
    f.add_argument("--out-dir", type=Path, required=True)
    e = sub.add_parser("e2")
    e.add_argument("--package-zip", type=Path, required=True)
    e.add_argument("--env-file", type=Path, required=True)
    e.add_argument("--out-dir", type=Path, required=True)
    c = sub.add_parser("classify")
    c.add_argument("--out-dir", type=Path, required=True)
    c.add_argument("--inputs", type=Path, default=None, help="E1 only; default RUN/inputs")
    c.add_argument("--verify", action="store_true", help="recompute and compare bytes instead of writing")
    p = sub.add_parser("publish")
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--e2-dir", type=Path, default=None)
    p.add_argument("--to", type=Path, required=True)
    a = ap.parse_args(argv)
    try:
        return {"gate": gate, "fetch": fetch, "e2": e2_cmd, "classify": classify, "publish": publish}[a.cmd](a)
    except Refused as r:
        print(json.dumps({"refused": r.reason}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
