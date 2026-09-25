"""Pure functions for the news-LLM direction study (standard library only).

Nothing here performs I/O, reads a clock or touches the network. Every rule the
protocol (`protocol.json`) preregisters is implemented once, here, and loaded by path
as module ``news_signal`` by `prepare.py`, `score.py`, `collect_auctions.py` and
`evaluate.py`. The name deliberately avoids ``signal.py``, which would shadow the
standard-library ``signal`` module (imported by subprocess and asyncio) whenever this
directory is on ``sys.path``.
"""

import ast
import bisect
import hashlib
import html
import json
import math
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
UTC = timezone.utc

# --------------------------------------------------------------------------------------
# Prompt (Lopez-Lira & Tang, arXiv 2304.07619v6, p.15) and the ChronoGPT-Instruct wrapper
# --------------------------------------------------------------------------------------

# Verbatim from the paper's PDF text layer, including its typographic quotes and the
# placeholders "company name" and "headline" (the paper substitutes them).
PAPER_PROMPT_VERBATIM = (
    "Forget all your previous instructions. Pretend you are a financial expert. You are "
    "a financial expert with stock recommendation experience. Answer “YES” if good "
    "news, “NO” if bad news, or “UNKNOWN” if uncertain in the first line. Then "
    "elaborate with one short and concise sentence on the next line. Is this headline "
    "good or bad for the stock price of company name in the short term?\n"
    "Headline: headline"
)

# The paper's prompt with ASCII double quotes and {company}/{headline} placeholders. Used
# only by the tested (non-operative) variants llt_alpaca and llt_upstream_wrapper; the
# operative variant is hlmw_alpaca (OPERATIVE_VARIANT, protocol D3).
PROMPT_TEMPLATE = (
    "Forget all your previous instructions. Pretend you are a financial expert. You are "
    "a financial expert with stock recommendation experience. Answer \"YES\" if good "
    "news, \"NO\" if bad news, or \"UNKNOWN\" if uncertain in the first line. Then "
    "elaborate with one short and concise sentence on the next line. Is this headline "
    "good or bad for the stock price of {company} in the short term?\n"
    "Headline: {headline}"
)

# Copied byte for byte from extract_response() in ChronoGPT_instruct.py (sha256 pinned in
# checkpoints.json), including the four-space indentation of its triple-quoted string.
CHRONO_SYSTEM_PROMPT = (
    "You are ChronoGPT, a large language model trained by ManelaLab at WashU.\n"
    "    Below is an instruction that describes a task.\n"
    "    Write a response that appropriately completes the request."
)


def build_prompt(company, headline):
    """The paper's prompt with the firm name and headline substituted."""
    return PROMPT_TEMPLATE.format(company=company, headline=headline)


def chrono_format(input_text):
    """The exact string extract_response() tokenizes before generation."""
    return f"\n\n### Instruction:\n{CHRONO_SYSTEM_PROMPT}\n{input_text}\n\n### Input:\n### Response:\n"


# He, Lv, Manela & Wu, "Instruction Tuning Chronologically Consistent Language Models",
# arXiv 2510.11677, section 2.2 (Alpaca-style SFT format, their Table 1 example) and
# section 3.3 (the prompt the model's authors use for trading portfolios, classified by
# the first generated word).
ALPACA_PREAMBLE = "Below is an instruction that describes a task. Write a response that appropriately completes the request."
HLMW_INSTRUCTION = "Classify this news headline as either FAVORABLE, or UNFAVORABLE, or UNCLEAR for the stock price of {company}."
# The paper's prompt without its final "Headline:" line, which moves to the Input field.
LLT_INSTRUCTION = PROMPT_TEMPLATE.split("\nHeadline:")[0]


def alpaca_format(instruction, input_text):
    return f"{ALPACA_PREAMBLE}\n\n### Instruction:\n{instruction}\n\n### Input:\n{input_text}\n\n### Response:\n"


YES_NO_LABELS = {"YES": 1, "NO": -1, "UNKNOWN": 0}
FAVORABLE_LABELS = {"FAVORABLE": 1, "UNFAVORABLE": -1, "UNCLEAR": 0}

# Prompt variants compared on the pre-freeze probe (protocol scoring.variant_selection).
# Each maps (company, headline) to the exact model input and has its own label set.
VARIANTS = {
    "llt_alpaca": {
        "build": lambda company, headline: alpaca_format(LLT_INSTRUCTION.format(company=company), headline),
        "template": alpaca_format(LLT_INSTRUCTION, "{headline}"),
        "labels": YES_NO_LABELS,
    },
    "hlmw_alpaca": {
        # a name ending in "." (e.g. "Acme Inc.") already closes the sentence
        "build": lambda company, headline: alpaca_format(
            HLMW_INSTRUCTION.format(company=company)[:-1] if company.endswith(".") else HLMW_INSTRUCTION.format(company=company),
            headline,
        ),
        "template": alpaca_format(HLMW_INSTRUCTION, "{headline}"),
        "labels": FAVORABLE_LABELS,
    },
    "llt_upstream_wrapper": {
        "build": lambda company, headline: chrono_format(build_prompt(company, headline)),
        "template": chrono_format(PROMPT_TEMPLATE),
        "labels": YES_NO_LABELS,
    },
}
VARIANT_PREFERENCE = ("llt_alpaca", "hlmw_alpaca", "llt_upstream_wrapper")
# Selected by outcome-blind label compliance (select_variant, rule v2) on the float32
# probe of 2026-09-25 (500 events, 50 per checkpoint by smallest sha256(event_id)):
# directional labels llt_alpaca 56/500, hlmw_alpaca 474/500, llt_upstream_wrapper
# 29/500. The rule was amended after the first (bfloat16) probe; v1 picked the same
# variant, so the amendment had no effect on the choice (protocol D17).
OPERATIVE_VARIANT = "hlmw_alpaca"


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def template_sha256(variant):
    return sha256_text(VARIANTS[variant]["template"])


def model_input(company, headline, variant=None):
    return VARIANTS[variant or OPERATIVE_VARIANT]["build"](company, headline)


TEMPLATE_SHA256 = template_sha256(OPERATIVE_VARIANT)

LABEL_SCORES = YES_NO_LABELS  # compatibility name only; the operative labels are VARIANTS[OPERATIVE_VARIANT]["labels"]
_LEADING_JUNK = re.compile(r"^[\s\"'`*_#>\-“”‘’(\[]+")
_ANSWER_PREFIX = re.compile(r"^(?:answer|response)\s*[:\-]\s*", re.I)
_FIRST_WORD = re.compile(r"^([A-Za-z]+)")
_FIRST_WORD_DONE = re.compile(r"^([A-Za-z]+)[^A-Za-z]")


def _normalized_first_line(raw_output):
    for line in str(raw_output).splitlines():
        text = line.strip()
        if not text:
            continue
        text = _LEADING_JUNK.sub("", text)
        text = _ANSWER_PREFIX.sub("", text)
        return _LEADING_JUNK.sub("", text)
    return None


def parse_label(raw_output, variant=None):
    """Map the model's first non-empty line to (label, score, parse_ok).

    Rule (protocol scoring.parse): take the first non-empty line, strip leading quotes,
    markdown and an optional "Answer:"/"Response:" prefix, then compare the first
    alphabetic word case-insensitively with the variant's label set (YES/NO/UNKNOWN or
    FAVORABLE/UNFAVORABLE/UNCLEAR). Anything else is a parse failure scored 0 (no
    position), recorded as label "PARSE_FAIL".
    """
    labels = VARIANTS[variant or OPERATIVE_VARIANT]["labels"]
    if raw_output is None:
        return "PARSE_FAIL", 0, False
    text = _normalized_first_line(raw_output)
    if text is None:
        return "PARSE_FAIL", 0, False
    match = _FIRST_WORD.match(text)
    if match is None:
        return "PARSE_FAIL", 0, False
    word = match.group(1).upper()
    if word in labels:
        return word, labels[word], True
    return "PARSE_FAIL", 0, False


# Operative score (deviation D22). The stored label of every score row stays the strict
# parse_label result (validated unchanged by evaluate.check_scores); the position a row
# takes comes from operative_score. The rule was chosen on 2026-09-25 from the output
# text alone (99.8% of strict PARSE_FAIL outputs begin with "UNF", e.g. "UNFLEXIBLE",
# "UNFRIENDLY", "UNF"); no price or return was read. The three label words have unique
# three-letter prefixes, so the prefix identifies the label the model started to write.
OPERATIVE_PREFIXES = {"UNF": ("UNFAVORABLE", -1), "FAV": ("FAVORABLE", 1), "UNC": ("UNCLEAR", 0)}


def operative_score(raw_output, stop=None):
    """(label, score, rule) from the first word's unique prefix: UNF -> -1, FAV -> +1,
    UNC -> 0, anything else PARSE_FAIL (0). rule is "exact" when the word is the full
    label, "prefix" when only the prefix matched, "none" otherwise. Context overflows
    are PARSE_FAIL."""
    if stop == "context_overflow" or raw_output is None:
        return "PARSE_FAIL", 0, "none"
    text = _normalized_first_line(raw_output)
    if text is None:
        return "PARSE_FAIL", 0, "none"
    match = _FIRST_WORD.match(text)
    if match is None:
        return "PARSE_FAIL", 0, "none"
    word = match.group(1).upper()
    hit = OPERATIVE_PREFIXES.get(word[:3])
    if hit is None:
        return "PARSE_FAIL", 0, "none"
    label, score = hit
    return label, score, "exact" if word == label else "prefix"


def label_decided(generated_text):
    """True once more tokens cannot change the parsed label.

    The label depends only on the first word of the first non-empty line, so decoding
    can stop when that word is followed by a non-letter or its line has ended.
    """
    stripped = generated_text.lstrip()
    if stripped and "\n" in stripped:
        return True
    # Only leading junk is removed here: a trailing space is what shows the word ended.
    text = _LEADING_JUNK.sub("", stripped)
    if re.match(r"^(?:answer|response)\s*[:\-]?\s*$", text, re.I):
        return False
    text = _LEADING_JUNK.sub("", _ANSWER_PREFIX.sub("", text))
    if not text:
        return False
    return bool(_FIRST_WORD_DONE.match(text)) or not text[0].isalpha()


def select_variant(probe_stats, min_directional_rate=0.50, min_directional_share=0.05):
    """Label-agnostic choice of the operative prompt variant (rule v2, protocol D17).

    probe_stats: variant -> {"n": events, "labels": {label: count}} from the same probe
    events scored with the final numerics (float32). A variant is eligible when events
    with a directional label (+1 or -1) are >= 50% of the probe and each direction is
    >= 5%. The first eligible variant in VARIANT_PREFERENCE wins; with none eligible,
    None (a blocker, not a fallback). Rule v1 (valid-label rate >= 0.90, measured in
    bfloat16) is superseded because float32 decoding turns many "UNFAVORABLE" answers
    into malformed "UNFLEXIBLE", which both rules score 0 anyway.
    """
    for name in VARIANT_PREFERENCE:
        stats = probe_stats.get(name)
        if not stats or not stats.get("n"):
            continue
        labels = VARIANTS[name]["labels"]
        n = stats["n"]
        shares = [stats["labels"].get(k, 0) / n for k, s in labels.items() if s != 0]
        if sum(shares) >= min_directional_rate and min(shares) >= min_directional_share:
            return name
    return None


# --------------------------------------------------------------------------------------
# Checkpoint mapping
# --------------------------------------------------------------------------------------

FIRST_CHECKPOINT_YEAR = 2015
LAST_CHECKPOINT_YEAR = 2024


def checkpoint_year(created_at_utc):
    """Headline in New York calendar year Y uses the (Y-1)-12-31 checkpoint.

    Headlines in 2025 and later use the 2024-12-31 checkpoint (the newest published).
    The year is taken in America/New_York so a headline stamped 2020-01-01T01:00Z
    (2019-12-31 evening in New York) maps to 2018-12-31, never to a checkpoint whose
    cutoff date is the headline's own date. Headlines before 2016 are out of scope.
    """
    year = as_utc(created_at_utc).astimezone(NY).year
    ckpt = min(year - 1, LAST_CHECKPOINT_YEAR)
    if ckpt < FIRST_CHECKPOINT_YEAR:
        raise ValueError(f"headline year {year} precedes the first checkpoint mapping")
    return ckpt


def checkpoint_repo(year):
    return f"manelalab/chrono-gpt-instruct-v1-{year}1231"


# --------------------------------------------------------------------------------------
# Timestamps, symbols, text normalization
# --------------------------------------------------------------------------------------


def as_utc(value):
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("naive datetime")
        return value.astimezone(UTC)
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise ValueError("timestamp without offset")
    return parsed.astimezone(UTC)


def parse_symbols(value):
    """The archive stores `symbols` as a string list, either JSON or a Python literal.

    Only a literal list of strings is accepted (``ast.literal_eval`` never executes code).
    Returns None when the field is not such a list.
    """
    if isinstance(value, list):
        items = value
    elif isinstance(value, str):
        text = value.strip()
        try:
            items = json.loads(text)
        except ValueError:
            try:
                items = ast.literal_eval(text)
            except (ValueError, SyntaxError):
                return None
    else:
        return None
    if not isinstance(items, (list, tuple)) or not all(isinstance(s, str) for s in items):
        return None
    out = []
    for s in items:
        s = s.strip().upper()
        if s and s not in out:
            out.append(s)
    return out


def clean_headline(text):
    """Headline as given to the model: HTML entities decoded, whitespace collapsed."""
    return re.sub(r"\s+", " ", html.unescape(text or "")).strip()


def normalize_headline(text):
    """Duplicate key: NFKC, entities decoded, lower case, non-alphanumerics to spaces."""
    text = unicodedata.normalize("NFKC", html.unescape(text or "")).lower()
    return re.sub(r"[^0-9a-z]+", " ", text).strip()


# Headlines that only report the stock's own price move (the paper drops RavenPack's
# 'stock-gain'/'stock-loss' categories). Deterministic approximation, deviation D5.
MOVEMENT_PATTERNS = (
    # D5 audit (2026-09-25): "sell" was removed (it matched "... Shares By Selling
    # Stockholders" offering news) and "up"/"down" may not be followed by "to" ("Offering
    # Of Up To $8.4M").
    r"\b(?:shares|stock|stocks)\b[^.]{0,40}\b(?:(?:trad|mov|ris|fall|soar|sink|surg|plung|jump|tumbl|climb|"
    r"slid|slip|spik|drop|slump|rall|skyrocket|rocket|crash|tank|gain)\w*|rose|fell|sank|"
    r"(?:down|up)(?!\s+to\b)|higher|lower)\b",
    r"\bwhat(?:'s|\s+is)\s+going\s+on\s+with\b",
    r"\binvested\s+(?:\$\s?\d[\d,]*\s+)?in\b[^.]{0,80}\b(?:years?|months?)\s+ago\b",
    r"\$\s?\d[\d,]*\s+invested\b",
    r"\b(?:shares|stock)\b[^.]{0,30}\b(?:hit|hits|hitting|reach|reaches|touch|touches|set|sets)\b"
    r"[^.]{0,30}\b(?:52[- ]week|all[- ]time|record)\s+(?:high|low)s?\b",
    r"\b(?:biggest|top)\s+(?:movers|gainers|losers)\b",
    r"\bmid[- ]?day\s+(?:movers|gainers|losers)\b",
    r"\b(?:pre[- ]?market|after[- ]hours|premarket|afterhours)\s+(?:movers|gainers|losers)\b",
    r"\bwhy\b[^.]{0,60}\b(?:shares|stock)\b[^.]{0,40}\b(?:are|is)\b",
    r"\b(?:unusual\s+)?options\s+activity\b",
    r"\b(?:gap|gaps|gapping)\s+(?:up|down)\b",
    r"\bhalted\b|\btrading\s+halt\b|\bresumes?\s+trading\b",
)
MOVEMENT_RE = re.compile("|".join(f"(?:{p})" for p in MOVEMENT_PATTERNS), re.I)


def is_movement_headline(text):
    return bool(MOVEMENT_RE.search(clean_headline(text)))


# Reused verbatim from blueprints/us-equities/broad-universe/coverage.py and scan.py so the
# instrument definition matches the earlier mover studies (deviation D6 explains the
# relation to CRSP share codes 10/11).
FUND_NAME_PATTERN = re.compile(r"ETF|ETN|Fund|Trust|Shares|ProShares|Direxion|iShares|SPDR|Index|Portfolio", re.I)
EXCLUSION_SUFFIX_RE = re.compile(r"\.(WS|W|U|R|RT)$")
LISTING_EXCHANGES = ("NYSE", "NASDAQ", "AMEX", "ARCA", "BATS")


# Extension for this study (deviation D6): security types the fund-name pattern misses
# because NASDAQ five-letter tickers carry no dotted suffix.
SECURITY_TYPE_PATTERN = re.compile(
    r"\b(?:Warrants?|Units?|Rights?|Preferred|Notes?|Debentures?|Depositary|Ordinary\s+Share|"
    r"Subordinated|Cert\.?|Certificates?|Perpetual)\b",
    re.I,
)


def is_primary_operating_company(symbol, name, exchange):
    if exchange not in LISTING_EXCHANGES:
        return False
    if EXCLUSION_SUFFIX_RE.search(symbol or ""):
        return False
    if not name or FUND_NAME_PATTERN.search(name) or SECURITY_TYPE_PATTERN.search(name):
        return False
    return True


_NAME_SUFFIXES = re.compile(
    r"(?:\s*[,-]?\s*(?:(?:Series|Class)\s+[A-Z0-9]+\s+)?(?:Common\s+Stock|Ordinary\s+Stock|Capital\s+Stock|"
    r"Subordinate\s+Voting\s+Stock|Voting\s+Stock|Stock)"
    r"(?:\s*,?\s*(?:par\s+value\s+)?\$?[0-9.]+\s*(?:par\s+value)?(?:\s+per\s+share)?)?\s*(?:\(.*\))?\s*)$",
    re.I,
)


_CLASS_TAIL = re.compile(r"\s+(?:Series|Class)\s+[A-Z0-9]+$", re.I)
_THE_TAIL = re.compile(r"\s*\(The\)$", re.I)


def clean_company_name(name):
    """Asset-master name without its security-type tail ("Apple Inc. Common Stock" -> "Apple Inc.")."""
    original = re.sub(r"\s+", " ", name or "").strip()
    text = original
    previous = None
    while previous != text:
        previous = text
        text = _NAME_SUFFIXES.sub("", text).strip().rstrip(",").strip()
        text = _CLASS_TAIL.sub("", text).strip()
        text = _THE_TAIL.sub("", text).strip()
    return text or original


# --------------------------------------------------------------------------------------
# Session calendar and timing windows
# --------------------------------------------------------------------------------------

OVERNIGHT = "overnight"
RTH = "rth"
EXCLUDED_PREMARKET = "excluded_0900_0930"
EXCLUDED_LATE = "excluded_last_30min"
OUTSIDE = "outside_calendar"

RTH_ENTRY_DELAY = timedelta(minutes=15)
RTH_LAST_RELEASE_BEFORE_CLOSE = timedelta(minutes=30)
OVERNIGHT_CUTOFF_HOUR = 9  # 09:00 New York, the paper's cutoff


@dataclass(frozen=True)
class Session:
    session: date
    open_utc: datetime
    close_utc: datetime
    early_close: bool

    @property
    def cutoff_utc(self):
        """09:00 America/New_York on the session date, DST-aware."""
        local = datetime(self.session.year, self.session.month, self.session.day, OVERNIGHT_CUTOFF_HOUR, 0, tzinfo=NY)
        return local.astimezone(UTC)


@dataclass(frozen=True)
class Window:
    kind: str
    session: date | None
    sub: str | None
    release_utc: datetime
    entry_utc: datetime | None
    exit_utc: datetime | None
    decision_cutoff_utc: datetime | None


class Calendar:
    """XNYS sessions from blueprints/us-equities/mover-v3/data/session-calendar.json."""

    def __init__(self, sessions):
        self.sessions = sorted(sessions, key=lambda s: s.session)
        self._closes = [s.close_utc for s in self.sessions]
        self._index = {s.session: i for i, s in enumerate(self.sessions)}

    @classmethod
    def from_calendar_json(cls, payload):
        cols = payload["columns"]
        idx = {c: cols.index(c) for c in ("session", "open_utc", "close_utc", "early_close")}
        rows = []
        for row in payload["sessions"]:
            rows.append(
                Session(
                    session=date.fromisoformat(row[idx["session"]]),
                    open_utc=as_utc(row[idx["open_utc"]]),
                    close_utc=as_utc(row[idx["close_utc"]]),
                    early_close=bool(row[idx["early_close"]]),
                )
            )
        return cls(rows)

    def index_of(self, session_date):
        return self._index[session_date]

    def get(self, session_date):
        return self.sessions[self._index[session_date]]

    def previous(self, session_date, count=1):
        i = self._index[session_date] - count
        if i < 0:
            return None
        return self.sessions[i]

    def prior_sessions(self, session_date, count):
        i = self._index[session_date]
        if i - count < 0:
            return None
        return [s.session for s in self.sessions[i - count:i]]

    def classify(self, created_at_utc):
        """Assign a release time to its trading window (protocol timing).

        With s the first session whose official close is after the release time t:
          [close(s-1), 09:00 NY on s)       -> overnight: enter at s's official open,
                                              exit at s's official close;
          [09:00 NY, open(s))               -> excluded (paper convention);
          [open(s), close(s) - 30 min)      -> RTH: enter at t + 15 min, exit at close(s);
          [close(s) - 30 min, close(s))     -> excluded (too little time to the close).
        Weekends, holidays and early closes follow from the calendar itself: a release
        after an early 13:00 close falls into the next session's overnight window.
        """
        t = as_utc(created_at_utc)
        i = bisect.bisect_right(self._closes, t)
        if i >= len(self.sessions):
            return Window(OUTSIDE, None, None, t, None, None, None)
        s = self.sessions[i]
        if i == 0 and t < s.cutoff_utc:
            # No previous close in the calendar: the window start is unknown.
            prior_ok = False
        else:
            prior_ok = True
        if t < s.cutoff_utc:
            if not prior_ok:
                return Window(OUTSIDE, None, None, t, None, None, None)
            sub = "pre_open" if t.astimezone(NY).date() == s.session else "post_close"
            return Window(OVERNIGHT, s.session, sub, t, s.open_utc, s.close_utc, s.cutoff_utc)
        if t < s.open_utc:
            return Window(EXCLUDED_PREMARKET, s.session, None, t, None, None, None)
        if t < s.close_utc - RTH_LAST_RELEASE_BEFORE_CLOSE:
            entry = t + RTH_ENTRY_DELAY
            return Window(RTH, s.session, "intraday", t, entry, s.close_utc, entry)
        return Window(EXCLUDED_LATE, s.session, None, t, None, None, None)


def timestamp_guard(window, updated_at_utc):
    """The archived text must already be in its final form at the decision cutoff.

    Alpaca does not guarantee that created_at is the publication time, and the archive
    stores the last version of each article. An article passes only when its
    updated_at is at or before the window's decision cutoff (overnight: strictly before
    09:00 NY on the session; RTH: at or before release + 15 min). Returns (ok, reason).
    """
    if window.kind not in (OVERNIGHT, RTH):
        return False, "not_tradable_window"
    if updated_at_utc is None:
        return False, "missing_updated_at"
    updated = as_utc(updated_at_utc)
    if window.kind == OVERNIGHT:
        ok = updated < window.decision_cutoff_utc
    else:
        ok = updated <= window.decision_cutoff_utc
    return (True, "ok") if ok else (False, "updated_after_cutoff")


# Second timestamp guard (prepare.py). News ids follow ingestion order, so an article
# cannot have entered the feed much before the articles with the next-lower ids. Its
# estimated ingestion time is the later of its own created_at and the 90th percentile of
# the created_at of the 100 articles with the next-lower ids; the article is dropped when
# that estimate is later than its window's decision cutoff (ingestion_guard).
INGESTION_PREDECESSORS = 100
INGESTION_QUANTILE = 0.90


def quantile_sorted(ordered, q):
    """Lower empirical quantile of an ascending list (element at floor(q * (n - 1)))."""
    return ordered[int(q * (len(ordered) - 1))]


def estimated_ingestion(predecessor_times_sorted, created_ts):
    """max(created_at, 90th percentile of the predecessors' created_at); epoch seconds."""
    if not predecessor_times_sorted:
        return created_ts
    return max(created_ts, quantile_sorted(predecessor_times_sorted, INGESTION_QUANTILE))


def ingestion_guard(window, ingestion_ts):
    """Same comparison as timestamp_guard, applied to the estimated ingestion time."""
    if window.kind not in (OVERNIGHT, RTH):
        return False, "not_tradable_window"
    cutoff = window.decision_cutoff_utc.timestamp()
    ok = ingestion_ts < cutoff if window.kind == OVERNIGHT else ingestion_ts <= cutoff
    return (True, "ok") if ok else (False, "ingested_after_cutoff")


# ---- Compatibility names (not used by this study since the 2026-09-25 review fixes).
# Kept because another builder imports this module by path; do not rely on them here.
ID_ORDER_GUARD_SECONDS = 3600
ID_ORDER_PREDECESSORS = 5
RTH_ENTRY_SEARCH_MINUTES = 5


def id_order_lag(predecessor_times, t):
    """Superseded guard-B statistic: t's lag behind the median of its predecessors (or None)."""
    if not predecessor_times:
        return None
    ordered = sorted(predecessor_times)
    return ordered[len(ordered) // 2] - t


def rth_entry_minute(entry_utc):
    """Superseded minute-bar entry: (NY date, ET minute) of the first full bar at/after entry."""
    t = as_utc(entry_utc)
    if t.second or t.microsecond:
        t = t.replace(second=0, microsecond=0) + timedelta(minutes=1)
    local = t.astimezone(NY)
    return local.date(), local.hour * 60 + local.minute


def pick_entry_bar(bars_by_minute, entry_minute):
    """Superseded: first bar in [entry_minute, entry_minute + 5) with a positive open."""
    for m in range(entry_minute, entry_minute + RTH_ENTRY_SEARCH_MINUTES):
        bar = bars_by_minute.get(m)
        if bar is not None and bar.get("o") and bar["o"] > 0:
            return m, float(bar["o"])
    return None
# ---- end of compatibility names


RTH_QUOTE_WINDOW = timedelta(seconds=60)


def rth_entry_quote(quotes, entry_utc):
    """First two-sided, uncrossed SIP quote stamped in [entry, entry + 60 s], else None.

    Returns {"bid", "ask", "t"}. The order is assumed to reach the market at the entry
    time and to fill against the first quote it meets: longs pay the ask, shorts receive
    the bid (rth_entry_price).
    """
    start = as_utc(entry_utc)
    end = start + RTH_QUOTE_WINDOW
    for q in quotes or []:
        if half_spread_fraction(q) is None or not q.get("t"):
            continue
        t = as_utc(q["t"])
        if start <= t <= end:
            return {"bid": float(q["bp"]), "ask": float(q["ap"]), "t": q["t"]}
    return None


def rth_entry_price(quote, side):
    """Ask for a long (+1), bid for a short (-1)."""
    if quote is None:
        return None
    return quote["ask"] if side == 1 else quote["bid"]


# --------------------------------------------------------------------------------------
# Short-sale restriction (SEC Rule 201), from information available before the decision
# --------------------------------------------------------------------------------------

SSR_DECLINE = 0.10


def ssr_carryover(prior_low_adj, prior2_close_adj):
    """Rule 201 in force on the trade session because it triggered on the prior session:
    the prior session's low was at least 10% below the close of the session before it
    (split-adjusted daily bars, both strictly before the trade session)."""
    if prior_low_adj is None or prior2_close_adj is None or prior2_close_adj <= 0:
        return False
    return prior_low_adj <= (1 - SSR_DECLINE) * prior2_close_adj


def ssr_flag(event, entry_quote=None):
    """True when a short on this event may be restricted under Rule 201.

    Overnight (entry at the open): only the carry-over from the prior session is knowable.
    RTH: the carry-over, or the entry quote's bid already 10% or more below the prior
    session's raw close (then the restriction has triggered for the day).
    """
    if event.get("ssr_carryover"):
        return True
    if event.get("window") == RTH and entry_quote is not None:
        prior = event.get("prior_close")
        if prior and entry_quote["bid"] <= (1 - SSR_DECLINE) * prior:
            return True
    return False


# --------------------------------------------------------------------------------------
# Novelty
# --------------------------------------------------------------------------------------

DUPLICATE_LOOKBACK = timedelta(hours=24)


class DuplicateTracker:
    """Per-symbol memory of normalized headlines over the prior 24 hours.

    Feed every parsed archive article (any number of symbols) in (created_at, id)
    order through `seen_recently` then `record`. An article is a duplicate for a
    symbol when an earlier-ordered article mentioning that symbol carried the same
    normalized headline within the 24 hours up to and including its release time.
    """

    def __init__(self, lookback=DUPLICATE_LOOKBACK):
        self.lookback = lookback
        self._by_symbol = {}

    def seen_recently(self, symbol, created_at_utc, norm):
        t = as_utc(created_at_utc)
        entries = self._by_symbol.get(symbol)
        if not entries:
            return False
        horizon = t - self.lookback
        while entries and entries[0][0] < horizon:
            entries.pop(0)
        return any(n == norm for _, n in entries)

    def record(self, symbols, created_at_utc, norm):
        t = as_utc(created_at_utc)
        for symbol in symbols:
            self._by_symbol.setdefault(symbol, []).append((t, norm))

    def prune_all(self, now_utc):
        """Forget entries older than the lookback for every symbol (memory bound only)."""
        horizon = as_utc(now_utc) - self.lookback
        for symbol in list(self._by_symbol):
            kept = [e for e in self._by_symbol[symbol] if e[0] >= horizon]
            if kept:
                self._by_symbol[symbol] = kept
            else:
                del self._by_symbol[symbol]


def first_per_window(events):
    """Keep the earliest (created_at, news_id) event per (symbol, session, window kind)."""
    best = {}
    for ev in events:
        key = (ev["symbol"], ev["session"], ev["window"])
        rank = (ev["created_at"], int(ev["news_id"]) if str(ev["news_id"]).isdigit() else str(ev["news_id"]))
        if key not in best or rank < best[key][0]:
            best[key] = (rank, ev)
    return [v[1] for _, v in sorted(best.items(), key=lambda kv: kv[1][0])]


# --------------------------------------------------------------------------------------
# Liquidity lanes
# --------------------------------------------------------------------------------------

LIQUID = "liquid"
SMALL = "small"
LOOKBACK_SESSIONS = 20
LIQUID_MIN_CLOSE = 5.0
LIQUID_MIN_MEDIAN_DV = 20_000_000.0
SMALL_MIN_CLOSE = 1.0
SMALL_MIN_MEDIAN_DV = 2_000_000.0


def lane_for(prior_close, median_dollar_volume, prior_bars_complete):
    """Lane from sessions strictly before the trade session.

    prior_close: raw close of the session immediately before the trade session;
    median_dollar_volume: median of raw close x raw volume over the 20 calendar sessions
    before the trade session; prior_bars_complete: all 20 of those sessions have a bar.
    """
    if not prior_bars_complete or prior_close is None or median_dollar_volume is None:
        return None
    if prior_close >= LIQUID_MIN_CLOSE and median_dollar_volume >= LIQUID_MIN_MEDIAN_DV:
        return LIQUID
    if prior_close >= SMALL_MIN_CLOSE and median_dollar_volume >= SMALL_MIN_MEDIAN_DV:
        return SMALL
    return None


# --------------------------------------------------------------------------------------
# Prices and costs
# --------------------------------------------------------------------------------------

OPEN_CONDITIONS = ("O", "Q")   # opening auction print, then official open
CLOSE_CONDITIONS = ("6", "M")  # closing auction print, then official close


# Tape codes that identify each current listing venue's own auction prints. Nasdaq
# prints appear as "Q" and, in older SIP data, as "T" (observed in the 2026-09-25 smoke
# collection: 2016 and 2019 Nasdaq names print only at "T").
LISTING_TAPE_CODES = {"NASDAQ": ("Q", "T"), "NYSE": ("N",), "AMEX": ("A",), "ARCA": ("P",), "BATS": ("Z",)}
ARCA_CODE = "P"


def _earliest(entries):
    e = min(entries, key=lambda e: e.get("t", ""))
    return float(e["p"]), e.get("c"), e.get("x")


def select_auction_price(entries, kind, listing_exchange):
    """Official auction price from one day's `o` (open) or `c` (close) entries.

    Order (protocol prices.auction_selection):
      1. the auction print (O open / 6 close) at a tape code of the current listing venue;
      2. else the auction print of the only venue other than NYSE Arca that has one
         (Arca runs its own auction for every symbol; a listing change since the event
         date leaves the historical venue as the remaining print);
      3. else the auction print of the only venue that has one;
      4. else the official-price condition (Q open / M close) at the listing venue.
    Returns (price, condition, exchange code) or None.
    """
    conditions = OPEN_CONDITIONS if kind == "open" else CLOSE_CONDITIONS
    codes = LISTING_TAPE_CODES.get(listing_exchange, ())
    valid = [e for e in entries or [] if isinstance(e.get("p"), (int, float)) and e["p"] > 0]
    prints = [e for e in valid if e.get("c") == conditions[0]]
    at_listing = [e for e in prints if e.get("x") in codes]
    if at_listing:
        return _earliest(at_listing)
    non_arca = [e for e in prints if e.get("x") != ARCA_CODE]
    if non_arca and len({e.get("x") for e in non_arca}) == 1:
        return _earliest(non_arca)
    if prints and len({e.get("x") for e in prints}) == 1:
        return _earliest(prints)
    official = [e for e in valid if e.get("c") == conditions[1] and e.get("x") in codes]
    if official:
        return _earliest(official)
    return None


def half_spread_fraction(quote):
    """(ask - bid) / (ask + bid) for a two-sided, uncrossed SIP quote, else None."""
    bid, ask = quote.get("bp"), quote.get("ap")
    if not isinstance(bid, (int, float)) or not isinstance(ask, (int, float)):
        return None
    if bid <= 0 or ask <= 0 or ask < bid:
        return None
    return (ask - bid) / (ask + bid)


def rate_on(rows, day, key):
    """Row value in force on `day` from a fees-v3 table (rows carry from/to ISO dates)."""
    iso = day.isoformat()
    for row in rows:
        if row["from"] <= iso and (row["to"] is None or iso <= row["to"]):
            return row
    earliest = min(rows, key=lambda r: r["from"])
    if iso < earliest["from"]:
        return earliest  # protocol costs.fees.before_first_row
    raise KeyError(f"no {key} row for {iso}")


def sale_fees_usd(fees, day, shares, price):
    """SEC Section 31 plus FINRA TAF on one sale (Alpaca commission is 0)."""
    sec = rate_on(fees["sec_section31"]["rows"], day, "sec")
    taf = rate_on(fees["finra_taf_covered_equity"]["rows"], day, "taf")
    notional = shares * price
    sec_usd = notional * sec["usd_per_million"] / 1_000_000.0
    taf_usd = 0.0
    if price >= taf["usd_per_share"]:
        taf_usd = min(shares * taf["usd_per_share"], taf["max_usd_per_trade"])
    return sec_usd + taf_usd


def position_net_return(side, entry_price, exit_price, day, fees, notional_usd, entry_cost_frac, exit_cost_frac):
    """Net return per dollar of one same-session round trip.

    side +1 long / -1 short. entry_cost_frac / exit_cost_frac are the preregistered
    per-side slippage (auction allowance, or half-spread plus allowance for RTH
    entries) applied adversely to the fill price. Fees fall on the sale: the exit of a
    long, the entry of a short. Shares are notional / entry fill (fractional allowed).
    """
    if side not in (1, -1):
        raise ValueError("side must be +1 or -1")
    if entry_price <= 0 or exit_price <= 0:
        raise ValueError("prices must be positive")
    entry_fill = entry_price * (1 + side * entry_cost_frac)
    exit_fill = exit_price * (1 - side * exit_cost_frac)
    shares = notional_usd / entry_fill
    if side == 1:
        fee = sale_fees_usd(fees, day, shares, exit_fill)
        pnl = shares * (exit_fill - entry_fill) - fee
    else:
        fee = sale_fees_usd(fees, day, shares, entry_fill)
        pnl = shares * (entry_fill - exit_fill) - fee
    return pnl / notional_usd


def gross_return(side, entry_price, exit_price):
    return side * (exit_price / entry_price - 1.0)


# --------------------------------------------------------------------------------------
# Portfolios and statistics
# --------------------------------------------------------------------------------------

MIN_NAMES_PER_LEG = 2


def daily_portfolios(positions):
    """Equal-weight daily legs and long-short from per-position returns.

    positions: iterable of dicts with keys session, side (+1/-1) and ret (the position's
    return per dollar, already signed for its side). A leg exists on a day only with at
    least two names. Confirmatory long_short = long leg + short leg and exists only when
    both legs exist. long_short_paper follows the paper's footnote 20 (the single existing
    leg when only one exists; descriptive), and single_leg marks those days.
    """
    by_day = {}
    for p in positions:
        d = by_day.setdefault(p["session"], {1: [], -1: []})
        d[p["side"]].append(p["ret"])
    out = {}
    for day, legs in sorted(by_day.items()):
        longs, shorts = legs[1], legs[-1]
        long_ret = sum(longs) / len(longs) if len(longs) >= MIN_NAMES_PER_LEG else None
        short_ret = sum(shorts) / len(shorts) if len(shorts) >= MIN_NAMES_PER_LEG else None
        both = long_ret is not None and short_ret is not None
        if long_ret is None and short_ret is None:
            paper = None
        else:
            paper = (long_ret or 0.0) + (short_ret or 0.0)
        out[day] = {
            "n_long": len(longs),
            "n_short": len(shorts),
            "long": long_ret,
            "short": short_ret,
            "long_short": long_ret + short_ret if both else None,
            "long_short_paper": paper,
            "single_leg": paper is not None and not both,
        }
    return out


def fixed_sequence(pvalues_in_order, alpha):
    """Test in order at alpha; stop at the first non-rejection. {name: rejected}."""
    out, open_ = {}, True
    for name, p in pvalues_in_order:
        rej = open_ and p is not None and not math.isnan(p) and p <= alpha
        out[name] = bool(rej)
        open_ = open_ and rej
    return out


def holm_reject(pvalues, alpha):
    """Holm step-down rejections at family level alpha. {name: rejected}."""
    adjusted = holm(pvalues)
    return {k: adjusted[k] <= alpha for k in pvalues}


def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def newey_west_t(series, lags):
    """t statistic of the mean with a Bartlett-kernel Newey-West variance."""
    x = [float(v) for v in series]
    n = len(x)
    if n < 2:
        return float("nan"), float("nan")
    mu = sum(x) / n
    e = [v - mu for v in x]
    gamma0 = sum(v * v for v in e) / n
    var = gamma0
    for lag in range(1, min(lags, n - 1) + 1):
        w = 1.0 - lag / (lags + 1.0)
        cov = sum(e[i] * e[i - lag] for i in range(lag, n)) / n
        var += 2.0 * w * cov
    if var <= 0:
        return float("nan"), float("nan")
    se = math.sqrt(var / n)
    return mu / se, se


def normal_sf(z):
    """One-sided upper-tail probability of a standard normal."""
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def holm(pvalues):
    """Holm step-down adjusted p-values for a dict name -> p (NaN treated as 1)."""
    items = sorted(((1.0 if (p is None or math.isnan(p)) else p), k) for k, p in pvalues.items())
    m = len(items)
    adjusted = {}
    running = 0.0
    for i, (p, k) in enumerate(items):
        running = max(running, min(1.0, (m - i) * p))
        adjusted[k] = running
    return adjusted
