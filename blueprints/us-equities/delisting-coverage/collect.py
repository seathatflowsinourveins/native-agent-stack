#!/usr/bin/env python3
"""Pre-2020 delisting coverage from the SEC EDGAR full-text index.

Read-only, first-party regulator source: the quarterly `form.idx` file under
`https://www.sec.gov/Archives/edgar/full-index/<YEAR>/QTR<N>/form.idx`,
filtered to Form 25 / 25-NSE (and their `/A` amendments) — the forms an
exchange files to deregister ("delist") a class of securities. This is
narrower than "every symbol that stopped trading": it covers exchange-
initiated deregistrations of securities registered under Section 12(b),
not every OTC drop, bankruptcy delisting reported only via other forms, or
a plain ticker change.

Pipeline:

1. Fetch and parse quarterly indexes; dedupe **per filing (accession
   number)**, not per CIK — a CIK can legitimately file more than one
   deregistration across the window (different security classes, or a
   refiled 25 after a withdrawn one). Raw row counts before dedupe and
   distinct-CIK-per-year counts are both recorded.
2. Classify every Form 25-NSE's primary document by security class
   (common/ordinary equity, preferred, debt, fund/ETF, warrant/right/unit,
   other/unknown) using ordered keyword rules (see `classify_security`'s
   docstring for the exact order and the measured misclassifications that
   order fixes). Headline "delisting" counts are the common/ordinary
   equity rows only; other classes are reported, never folded into the
   headline. This is a keyword classification over every in-scope
   document, not a verified/exhaustive ground truth -- residual
   misclassification is expected and reported (`equity_classification`'s
   `reclassification_from_round2` shows how many documents' class changed
   from the previous rule order alone). Per-document classifications
   (accession, CIK, company, class, matched rule, description hash) are
   persisted under `evidence/artifacts/pre-2020-delisting/` so the audit
   trail does not depend on the local work directory.
3. Draw a seeded sample from the common/ordinary-equity subset only and,
   for each event: resolve a ticker (in priority order — text embedded in
   the primary document itself, a normalized-company-name CANDIDATE match
   against Alpaca's inactive US-equity assets -- not a confirmed identity
   link -- then the filer's *current* data.sec.gov submissions tickers as
   a last resort, flagged as reuse risk since it is not point-in-time) and
   check, read-only, whether Alpaca SIP daily bars exist before the
   delisting date **and stop within 10 trading days after it**. Bars that
   continue well past the filing are flagged and never counted as
   coverage, whatever the underlying cause (a different security, a
   reused ticker, or a misclassified/mis-resolved event); the receipt
   states plainly how many sampled events actually had confirmed coverage.

Every fetched file (index, primary document, submissions record) is cached
under `--work-dir` (outside the repo) with its URL, sha256, byte count and
*original* fetch timestamp (persisted in a cache sidecar) recorded in the
receipt; a run that reads from cache never presents that read as a new
fetch (see `record_source`).
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import html
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

EDGAR_HOST = "https://www.sec.gov"
FULL_INDEX_PATH = "/Archives/edgar/full-index/{year}/QTR{quarter}/form.idx"
SUBMISSIONS_PATH = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
MAX_REQUESTS_PER_SECOND = 5
MAX_RETRIES = 5

# Form types that represent an exchange's deregistration ("delisting") of a
# class of securities under Section 12(b), plus their amendments.
DELISTING_FORMS = ("25", "25-NSE", "25/A", "25-NSE/A")

LINE_PATTERN = re.compile(
    r"^(?P<form>\S+(?:\s\S+)*?)\s{2,}(?P<company>.+?)\s+(?P<cik>\d{1,10})\s+"
    r"(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<filename>\S+)\s*$"
)
ACCESSION_PATTERN = re.compile(r"(\d{10}-\d{2}-\d{6})")

# Best-effort fallback: some primary documents may spell out a trading
# symbol near the words "Trading Symbol(s)" (e.g. "Title of each class ...
# Trading Symbol(s) ... XYZ"). Measured on an initial 40-document probe
# (2016-2019 Form 25-NSE filings, both the older HTML free-text format and
# the current `notificationOfRemoval` XML format): 0/40 documents contained
# this text at all -- the XML schema carries only `descriptionClassSecurity`
# (a security description, not a ticker) and the older HTML format uses a
# "(Description of class of securities)" caption with no separate symbol
# field either. This regex is kept as a defensive fallback for the
# untested remainder of the corpus and any future filing that does include
# such text, allowing up to 40 characters of intervening punctuation/markup
# between the phrase and the candidate symbol; it should not be assumed to
# contribute meaningfully to resolution (see `sample_probe` in the receipt
# for the measured rate on the actual run).
SYMBOL_PATTERN = re.compile(r"[Tt]rading\s+[Ss]ymbol[s]?\b.{0,40}?\b([A-Z]{1,5})\b", re.DOTALL)

DESCRIPTION_XML_PATTERN = re.compile(
    r"<descriptionClassSecurity>(.*?)</descriptionClassSecurity>", re.IGNORECASE | re.DOTALL
)
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
DESCRIPTION_CAPTION = "(Description of class of securities)"

FUND_KEYWORDS = ("exchange-traded fund", "exchange traded fund", " etf", "unit investment trust",
                  "closed-end fund", "closed end fund")
# "Common Shares of Beneficial Interest" (or similar "beneficial interest"
# language) from a fund-style issuer is a fund/ETF unit, not operating-
# company common equity, even though "common" appears in the text. Signal
# is read from either the description or the company name (round-3 fix:
# measured misclassifications of fund-style issuers as common equity).
BENEFICIAL_INTEREST_KEYWORDS = ("beneficial interest",)
FUND_STYLE_ISSUER_KEYWORDS = ("fund", "trust", "income", "municipal", "closed-end", "closed end", "portfolio")
DEBT_KEYWORDS = ("notes", "note due", "bond", "debenture", "bonds")
PREFERRED_KEYWORDS = ("preferred", "preference")
# Warrants, rights (including "purchase rights" -- a shareholder-rights
# ("poison pill") plan is commonly titled "Common Stock Purchase Rights",
# which contains the literal substring "common stock" but is not equity)
# and units must be checked BEFORE common-equity keywords (round-3 fix:
# measured misclassification of "Common Stock Purchase Rights" as common
# equity purely because it names the underlying common stock).
WARRANT_RIGHT_UNIT_KEYWORDS = ("warrant", "purchase right", "purchase rights", "right", "unit")
COMMON_KEYWORDS = ("common stock", "common shares", "ordinary share", "ordinary shares",
                    "class a common", "class b common", "class c common", "depositary share",
                    "depositary shares", "capital stock")

COMPANY_SUFFIX_WORDS = {"INC", "INCORPORATED", "CORP", "CORPORATION", "CO", "COMPANY", "LLC",
                         "LTD", "LIMITED", "PLC", "LP", "TRUST", "HOLDINGS", "HOLDING", "GROUP", "THE"}
COMPANY_NORMALIZE_PATTERN = re.compile(r"[^A-Z0-9 ]")

# National securities exchanges that file Form 25-NSE on an issuer's behalf
# (self-listed under their own CIK in EDGAR's index). Used as a name-based
# fallback when the accession's filer-CIK prefix does not match any row's
# CIK (round-3 fix: the filer-CIK-prefix method alone left ~70 duplicate
# groups unresolved and falling back to an arbitrary row).
EXCHANGE_NAME_KEYWORDS = (
    "STOCK EXCHANGE", "NASDAQ", "NYSE", "CBOE", "IEX", "INVESTORS EXCHANGE",
    "BATS", "BOX EXCHANGE", "MIAMI INTERNATIONAL SECURITIES", "PHLX", "ARCA", "AMEX",
    "CHICAGO STOCK EXCHANGE", "NATIONAL STOCK EXCHANGE",
)


def is_exchange_row(record: dict) -> bool:
    name = (record.get("company") or "").upper()
    return any(k in name for k in EXCHANGE_NAME_KEYWORDS)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def quarters(start_year: int, start_q: int, end_year: int, end_q: int):
    year, quarter = start_year, start_q
    while (year, quarter) <= (end_year, end_q):
        yield year, quarter
        quarter += 1
        if quarter > 4:
            quarter = 1
            year += 1


class RateLimiter:
    def __init__(self, max_per_second: float):
        self.min_interval = 1.0 / max_per_second
        self._last = 0.0

    def wait(self):
        now = time.monotonic()
        elapsed = now - self._last
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last = time.monotonic()


def http_get(url: str, headers: dict, limiter: RateLimiter) -> bytes:
    delay = 1.0
    for attempt in range(1, MAX_RETRIES + 1):
        limiter.wait()
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read()
                if response.headers.get("Content-Encoding", "").lower() == "gzip":
                    raw = gzip.decompress(raw)
                return raw
        except urllib.error.HTTPError as exc:
            if exc.code == 429 or 500 <= exc.code < 600:
                if attempt == MAX_RETRIES:
                    raise RuntimeError(f"HTTP {exc.code} after {attempt} attempts: {url}") from exc
                time.sleep(delay)
                delay *= 2
                continue
            raise RuntimeError(f"HTTP {exc.code} fetching {url}") from exc
        except Exception as exc:  # network failure
            if attempt == MAX_RETRIES:
                raise RuntimeError(f"network failure after {attempt} attempts fetching {url}: {type(exc).__name__}") from exc
            time.sleep(delay)
            delay *= 2
    raise RuntimeError(f"unreachable: {url}")


def record_source(sources: list, url: str, raw: bytes, cache_path, fetched_at, cache_read_at):
    """`fetched_at` must be the original network-fetch time, never the
    current run's clock on a cache hit; `cache_read_at` is set separately
    when this run read the bytes from disk instead of the network. If a
    cache hit has no recorded original fetch time (e.g. cached by a run
    before this provenance fix existed), `fetched_at` is "unknown" rather
    than being back-filled with the current time."""
    sources.append({
        "url": url,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "cache_path": str(cache_path) if cache_path else None,
        "fetched_at": fetched_at if fetched_at else "unknown",
        "cache_read_at": cache_read_at,
    })


def fetch_cached(url: str, cache_path: Path, headers: dict, limiter: RateLimiter, sources: list) -> bytes:
    """Fetch `url`, using `cache_path` as an on-disk cache, and always
    record a source entry so the run is replayable even on a cache hit.
    The original network-fetch timestamp is persisted in a `.meta.json`
    sidecar next to the cached file, so a later run reading from cache can
    report the true `fetched_at` instead of presenting the cache read as a
    new fetch (round-3 fix)."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path = cache_path.with_name(cache_path.name + ".meta.json")
    if cache_path.exists():
        raw = cache_path.read_bytes()
        cache_read_at = utc_now()
        fetched_at = None
        if meta_path.exists():
            try:
                fetched_at = json.loads(meta_path.read_text(encoding="utf-8")).get("fetched_at")
            except (json.JSONDecodeError, OSError):
                fetched_at = None
        record_source(sources, url, raw, cache_path, fetched_at=fetched_at, cache_read_at=cache_read_at)
    else:
        fetched_at = utc_now()
        raw = http_get(url, headers, limiter)
        cache_path.write_bytes(raw)
        try:
            meta_path.write_text(json.dumps({"url": url, "fetched_at": fetched_at}), encoding="utf-8")
        except OSError:
            pass
        record_source(sources, url, raw, cache_path, fetched_at=fetched_at, cache_read_at=None)
    return raw


def fetch_quarter_index(year: int, quarter: int, work_dir: Path, headers: dict, limiter: RateLimiter,
                         sources: list) -> Path:
    cache_path = work_dir / f"{year}QTR{quarter}.form.idx"
    url = EDGAR_HOST + FULL_INDEX_PATH.format(year=year, quarter=quarter)
    fetch_cached(url, cache_path, headers, limiter, sources)
    return cache_path


def extract_accession(filename: str) -> str:
    match = ACCESSION_PATTERN.search(filename)
    return match.group(1) if match else filename


def parse_form_idx(path: Path, wanted_forms: set) -> list:
    records = []
    started = False
    with path.open("r", encoding="latin-1", errors="replace") as handle:
        for line in handle:
            stripped = line.rstrip("\n")
            if not started:
                if stripped.startswith("---"):
                    started = True
                continue
            if not stripped.strip():
                continue
            match = LINE_PATTERN.match(stripped)
            if not match:
                continue
            form = match.group("form").strip()
            if form not in wanted_forms:
                continue
            filename = match.group("filename").strip()
            records.append({
                "form": form,
                "company": match.group("company").strip(),
                "cik": int(match.group("cik")),
                "date_filed": match.group("date"),
                "filename": filename,
                "accession": extract_accession(filename),
            })
    if not started:
        raise RuntimeError(f"malformed form.idx (no header separator found): {path}")
    if not records:
        raise RuntimeError(f"parsed 0 delisting-form rows from {path}; treating as a fetch/parse "
                            "failure rather than a genuine zero-filing quarter")
    return records


def collect_index(start_year: int, start_q: int, end_year: int, end_q: int, work_dir: Path, headers: dict,
                   limiter: RateLimiter) -> tuple:
    sources = []
    all_records = []
    for year, quarter in quarters(start_year, start_q, end_year, end_q):
        cache_path = fetch_quarter_index(year, quarter, work_dir, headers, limiter, sources)
        records = parse_form_idx(cache_path, set(DELISTING_FORMS))
        for record in records:
            record["quarter"] = f"{year}Q{quarter}"
        all_records.extend(records)
    return all_records, sources


def dedupe_by_accession(records: list) -> tuple:
    """Dedupe per filing (accession number), not per CIK: a CIK can
    legitimately file more than one deregistration in the window (separate
    security classes, or a refiled 25 after a withdrawn one), and each such
    filing must be counted. Only literal duplicate index rows (same
    accession appearing twice) are collapsed. Amendments (`/A` forms) are
    kept as their own accession-deduped list, never merged into a base
    filing's date. Returns (base_deduped, amendments_deduped, raw_count,
    duplicate_count, fallback_stats)."""
    raw_count = len(records)
    base = [r for r in records if not r["form"].endswith("/A")]
    amendments = [r for r in records if r["form"].endswith("/A")]

    def dedupe_group(group):
        by_accession = defaultdict(list)
        for record in group:
            by_accession[record["accession"]].append(record)
        deduped = []
        duplicates = 0
        fallback_groups = 0
        fallback_changed = 0
        for accession, rows in sorted(by_accession.items()):
            duplicates += len(rows) - 1
            if len(rows) == 1:
                deduped.append(rows[0])
                continue
            # 25-NSE is filed by the exchange on the issuer's behalf, and
            # EDGAR's full index cross-lists the same accession once under
            # the exchange's own CIK and once under the delisted issuer's
            # CIK (measured: 444/444 duplicate 25-NSE rows in a sampled
            # quarter were exactly this pattern; plain issuer-filed Form 25
            # never duplicates). Keeping the exchange's self-referential
            # row would corrupt the company/CIK fields for every 25-NSE
            # record, so prefer the row whose CIK is not the filer's own.
            filer_cik = filer_cik_from_accession(accession)
            row_ciks = {r["cik"] for r in rows}
            if filer_cik in row_ciks:
                issuer_rows = [r for r in rows if r["cik"] != filer_cik]
                chosen = issuer_rows[0] if issuer_rows else rows[0]
            else:
                # No row's CIK equals the accession's filer-CIK prefix at
                # all (e.g. an amendment accession filed under yet another
                # CIK, or an unusual filer arrangement) -- the prefix
                # method cannot isolate a row here. Fall back to
                # identifying the exchange's self-referential row by name
                # and keeping the other(s), rather than an arbitrary pick.
                fallback_groups += 1
                non_exchange_rows = [r for r in rows if not is_exchange_row(r)]
                fallback_rows = non_exchange_rows if non_exchange_rows else rows
                if fallback_rows[0] is not rows[0]:
                    fallback_changed += 1
                chosen = fallback_rows[0]
            deduped.append(chosen)
        return deduped, duplicates, fallback_groups, fallback_changed

    base_deduped, base_dupes, base_fallback_groups, base_fallback_changed = dedupe_group(base)
    amendments_deduped, amend_dupes, amend_fallback_groups, amend_fallback_changed = dedupe_group(amendments)
    fallback_stats = {
        "groups_using_name_fallback": base_fallback_groups + amend_fallback_groups,
        "groups_where_fallback_changed_the_pick": base_fallback_changed + amend_fallback_changed,
    }
    return base_deduped, amendments_deduped, raw_count, base_dupes + amend_dupes, fallback_stats


def filer_cik_from_accession(accession: str):
    try:
        return int(accession.split("-")[0])
    except (ValueError, IndexError):
        return None


def counts_by_year_form(records: list) -> dict:
    counts = defaultdict(Counter)
    for record in records:
        year = record["date_filed"][:4]
        counts[year][record["form"]] += 1
    return {year: dict(form_counts) for year, form_counts in sorted(counts.items())}


def distinct_ciks_by_year(records: list) -> dict:
    ciks = defaultdict(set)
    for record in records:
        ciks[record["date_filed"][:4]].add(record["cik"])
    return {year: len(cik_set) for year, cik_set in sorted(ciks.items())}


def normalize_company_name(name: str) -> str:
    text = (name or "").upper()
    text = COMPANY_NORMALIZE_PATTERN.sub(" ", text)
    tokens = [t for t in text.split() if t and t not in COMPANY_SUFFIX_WORDS]
    return " ".join(tokens)


def extract_description(raw_text: str) -> str:
    xml_match = DESCRIPTION_XML_PATTERN.search(raw_text)
    if xml_match:
        text = html.unescape(xml_match.group(1))
        return re.sub(r"\s+", " ", text).strip()
    # Older free-text HTML format: the description paragraph immediately
    # precedes the "(Description of class of securities)" caption. Strip
    # tags, collapse whitespace, and take a bounded window of text before
    # the caption as a best-effort (approximate) candidate.
    plain = HTML_TAG_PATTERN.sub(" ", raw_text)
    plain = html.unescape(plain)
    plain = re.sub(r"\s+", " ", plain).strip()
    idx = plain.find(DESCRIPTION_CAPTION)
    if idx == -1:
        return ""
    before = plain[:idx].strip()
    return before[-200:].strip()


def extract_symbol_from_text(raw_text: str) -> str:
    match = SYMBOL_PATTERN.search(raw_text)
    return match.group(1) if match else ""


def classify_security(description: str, company_name: str) -> tuple:
    """Classify a Form 25-NSE security description into one of:
    common_ordinary_equity, preferred, debt, fund_etf, warrant_right_unit,
    other, unknown (no description could be extracted). Returns
    (security_class, matched_rule) so every classification is auditable.

    Priority order (first match wins), fixed in round 3 from measured
    misclassifications:

    1. fund_etf -- explicit ETF/fund-structure keywords, checked first
       because ETF descriptions can contain "bond"/"notes" describing the
       underlying strategy, not the security's own legal form.
    2. fund_etf -- "beneficial interest" language (e.g. "Common Shares of
       Beneficial Interest") from a fund-style issuer (name or description
       signals fund/trust/income/municipal/closed-end/portfolio). Measured:
       without this rule, fund-style beneficial-interest shares were
       misclassified as common equity purely because "common" appears in
       the text.
    3. debt -- notes/bonds/debentures.
    4. warrant_right_unit -- warrants, rights (including "purchase
       rights"), units. Checked BEFORE preferred and common equity because
       a shareholder-rights ("poison pill") plan is commonly titled
       "Common Stock Purchase Rights" and a preferred/warrant unit can
       equally name an underlying common share; the description containing
       "common stock" does not make the security itself common equity.
       Measured: without this ordering, "Common Stock Purchase Rights"
       filings were misclassified as common equity.
    5. preferred -- "preferred" or "preference" (e.g. "Preference Share
       ADS"), also checked before common equity for the same reason.
    6. common_ordinary_equity -- only reached once none of the above
       matched.
    7. other -- description extracted but none of the rules matched.
    8. unknown -- no description could be extracted at all.
    """
    desc = (description or "").lower()
    name = (company_name or "").lower()
    if not description:
        return "unknown", "no_description_extracted"
    if any(k in desc or k in name for k in FUND_KEYWORDS):
        return "fund_etf", "fund_etf_keyword"
    if (any(k in desc for k in BENEFICIAL_INTEREST_KEYWORDS)
            and any(k in desc or k in name for k in FUND_STYLE_ISSUER_KEYWORDS)):
        return "fund_etf", "beneficial_interest_fund_style_issuer"
    if any(k in desc for k in DEBT_KEYWORDS):
        return "debt", "debt_keyword"
    if any(k in desc for k in WARRANT_RIGHT_UNIT_KEYWORDS):
        return "warrant_right_unit", "warrant_right_unit_keyword"
    if any(k in desc for k in PREFERRED_KEYWORDS):
        return "preferred", "preferred_keyword"
    if any(k in desc for k in COMMON_KEYWORDS):
        return "common_ordinary_equity", "common_keyword"
    return "other", "no_keyword_matched"


def classify_security_round2_compat(description: str, company_name: str) -> str:
    """Reproduces the round-2 classification rule (common-equity keywords
    checked before warrant/right/unit; no fund-style beneficial-interest
    rule; "preference" not recognized) verbatim, used only to compute the
    round-2 -> round-3 reclassification diff reported in the receipt. Not
    part of the live classification pipeline."""
    desc = (description or "").lower()
    name = (company_name or "").lower()
    if not description:
        return "unknown"
    if any(k in desc or k in name for k in FUND_KEYWORDS):
        return "fund_etf"
    if any(k in desc for k in DEBT_KEYWORDS):
        return "debt"
    if "preferred" in desc:
        return "preferred"
    if re.match(r"^\s*units?\b", desc, re.IGNORECASE):
        return "warrant_right_unit"
    if any(k in desc for k in COMMON_KEYWORDS):
        return "common_ordinary_equity"
    if any(k in desc for k in ("warrant", "right")):
        return "warrant_right_unit"
    return "other"


def fetch_primary_document(record: dict, headers: dict, limiter: RateLimiter, work_dir: Path,
                            sources: list, doc_cache: dict) -> str:
    """Fetch (or reuse from `doc_cache`/on-disk cache) a filing's primary
    document text. Returns "" on fetch failure rather than raising, so one
    bad document does not abort a batch pass."""
    accession = record["accession"]
    if accession in doc_cache:
        return doc_cache[accession]
    cache_path = work_dir / "docs" / f"{record['cik']}-{Path(record['filename']).name}"
    url = f"{EDGAR_HOST}/Archives/{record['filename']}"
    try:
        raw = fetch_cached(url, cache_path, headers, limiter, sources)
        text = raw.decode("latin-1", errors="replace")
    except RuntimeError:
        text = ""
    doc_cache[accession] = text
    return text


def select_classification_targets(nse_records: list, seed: int, sample_2016_2018: bool, sample_size: int = 400):
    """Return (targets, method_note, coverage_stats). When
    `sample_2016_2018` is False (default), every 25-NSE record is a
    target -- feasible at the mandated <=5 req/s SEC rate for ~2,000
    documents in a few minutes. When True, classifies all of 2019 plus a
    seeded sample of `sample_size` from 2016-2018, per-year population
    sizes recorded so the sampled years' headline counts can be reported
    as estimates alongside the measured sample."""
    by_year = defaultdict(list)
    for record in nse_records:
        by_year[record["date_filed"][:4]].append(record)
    population_by_year = {year: len(records) for year, records in sorted(by_year.items())}
    if not sample_2016_2018:
        targets = list(nse_records)
        return targets, "full_classification", population_by_year, {}

    rng = random.Random(seed)
    targets = []
    sampled_counts = {}
    for year, records in sorted(by_year.items()):
        if year == "2019":
            targets.extend(records)
            sampled_counts[year] = len(records)
        else:
            sample = rng.sample(records, min(sample_size, len(records)))
            targets.extend(sample)
            sampled_counts[year] = len(sample)
    return targets, "all_2019_plus_seeded_400_sample_2016_2018", population_by_year, sampled_counts


def classify_nse_filings(targets: list, headers: dict, limiter: RateLimiter, work_dir: Path, sources: list,
                          doc_cache: dict) -> list:
    classified = []
    for record in targets:
        text = fetch_primary_document(record, headers, limiter, work_dir, sources, doc_cache)
        description = extract_description(text) if text else ""
        symbol = extract_symbol_from_text(text) if text else ""
        security_class, matched_rule = classify_security(description, record["company"])
        round2_class = classify_security_round2_compat(description, record["company"])
        description_sha256 = hashlib.sha256(description.encode("utf-8")).hexdigest() if description else None
        used_xml = bool(DESCRIPTION_XML_PATTERN.search(text)) if text else False
        classified.append({
            **record,
            "description": description,
            "description_sha256": description_sha256,
            "description_extraction_method": "xml" if used_xml else ("html_fallback" if description else "none"),
            "security_class": security_class,
            "matched_rule": matched_rule,
            "security_class_round2": round2_class,
            "ticker_from_document": symbol,
        })
    return classified


def reclassification_diff(classified: list) -> dict:
    """Round-2 -> round-3 transition counts: how many documents moved, and
    between which classes, purely from the rule-order/keyword fix (the
    underlying extracted descriptions are unchanged)."""
    moved = [r for r in classified if r["security_class"] != r["security_class_round2"]]
    transitions = Counter((r["security_class_round2"], r["security_class"]) for r in moved)
    return {
        "documents_compared": len(classified),
        "documents_moved": len(moved),
        "transitions": {f"{frm} -> {to}": count for (frm, to), count in
                         sorted(transitions.items(), key=lambda kv: -kv[1])},
    }


def write_classification_artifact(classified: list, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [{
        "accession": r["accession"],
        "cik": r["cik"],
        "company": r["company"],
        "date_filed": r["date_filed"],
        "security_class": r["security_class"],
        "matched_rule": r["matched_rule"],
        "security_class_round2": r["security_class_round2"],
        "description_extraction_method": r["description_extraction_method"],
        "description_sha256": r["description_sha256"],
    } for r in classified]
    path.write_text(json.dumps({
        "id": "pre-2020-delisting-per-document-classifications",
        "documents": rows,
        "generated_utc": utc_now(),
    }, indent=2) + "\n", encoding="utf-8")


def class_counts_by_year(classified: list) -> dict:
    counts = defaultdict(Counter)
    for record in classified:
        counts[record["date_filed"][:4]][record["security_class"]] += 1
    return {year: dict(c) for year, c in sorted(counts.items())}


def build_inactive_asset_index(trading_client, request_cls, status_enum, asset_class_enum) -> dict:
    request = request_cls(status=status_enum.INACTIVE, asset_class=asset_class_enum.US_EQUITY)
    assets = trading_client.get_all_assets(request)
    index = {}
    for asset in assets:
        key = normalize_company_name(getattr(asset, "name", "") or "")
        if not key:
            continue
        index.setdefault(key, []).append(asset.symbol)
    return index


def build_alpaca_clients():
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import GetAssetsRequest
    from alpaca.trading.enums import AssetStatus, AssetClass

    api_key = os.environ["APCA_API_KEY_ID"]
    secret_key = os.environ["APCA_API_SECRET_KEY"]
    data_client = StockHistoricalDataClient(api_key, secret_key)
    trading_client = TradingClient(api_key, secret_key, paper=True)
    inactive_index = build_inactive_asset_index(trading_client, GetAssetsRequest, AssetStatus, AssetClass)
    return {
        "data_client": data_client,
        "request_cls": StockBarsRequest,
        "timeframe": TimeFrame.Day,
        "inactive_index": inactive_index,
        "inactive_asset_count": sum(len(v) for v in inactive_index.values()),
    }


def count_trading_days(start_date, end_date) -> int:
    """Weekday count strictly after `start_date` through `end_date`
    (inclusive), with no exchange-holiday calendar. This OVER-counts true
    trading days relative to the real exchange calendar, because market
    holidays (e.g. Thanksgiving, Christmas) are weekdays that get counted
    here even though no trading occurred. The bias therefore runs toward
    `bars_continue_after_delisting` firing *more* readily, not less --
    documented as a limitation, not a conservative under-count."""
    if end_date <= start_date:
        return 0
    days = 0
    current = start_date + timedelta(days=1)
    while current <= end_date:
        if current.weekday() < 5:
            days += 1
        current += timedelta(days=1)
    return days


def _bars_last_date(bars):
    try:
        frame = bars.df
    except Exception:
        return None, 0
    if frame is None or len(frame) == 0:
        return None, 0
    index = frame.index
    try:
        timestamps = index.get_level_values(-1)
    except AttributeError:
        timestamps = index
    last_ts = max(timestamps)
    last_date = last_ts.date() if hasattr(last_ts, "date") else last_ts
    return last_date, len(frame)


def probe_alpaca_bars(ticker: str, delisting_date: str, alpaca_module) -> dict:
    """Read-only check: SIP daily bars exist in the 60 days before
    `delisting_date`, AND stop within 10 trading days after it. Bars found
    to continue well past the filing indicate a different or reused
    security and are flagged; `coverage_confirmed` is only True when both
    conditions hold, so a ticker match alone is never counted as coverage.
    """
    end = datetime.strptime(delisting_date, "%Y-%m-%d").date()
    pre_start = end - timedelta(days=60)
    client = alpaca_module["client"]
    request_cls = alpaca_module["request_cls"]
    timeframe = alpaca_module["timeframe"]

    pre_request = request_cls(symbol_or_symbols=[ticker], timeframe=timeframe, start=pre_start, end=end, feed="sip")
    pre_bars = client.get_stock_bars(pre_request)
    _, pre_count = _bars_last_date(pre_bars)
    has_bars_before = pre_count > 0

    post_start = end
    post_end = end + timedelta(days=45)
    post_request = request_cls(symbol_or_symbols=[ticker], timeframe=timeframe, start=post_start, end=post_end,
                                feed="sip")
    post_bars = client.get_stock_bars(post_request)
    last_post_date, post_count = _bars_last_date(post_bars)
    trading_days_after = count_trading_days(end, last_post_date) if last_post_date else 0
    bars_continue_after_delisting = trading_days_after > 10

    coverage_confirmed = has_bars_before and not bars_continue_after_delisting

    return {
        "ticker": ticker,
        "pre_window_start": pre_start.isoformat(),
        "pre_window_end": end.isoformat(),
        "pre_bar_count": pre_count,
        "has_bars_before": has_bars_before,
        "post_window_end": post_end.isoformat(),
        "post_bar_count": post_count,
        "last_post_bar_date": last_post_date.isoformat() if last_post_date else None,
        "trading_days_after_delisting": trading_days_after,
        "bars_continue_after_delisting": bars_continue_after_delisting,
        "coverage_confirmed": coverage_confirmed,
    }


def resolve_ticker(record: dict, headers: dict, limiter: RateLimiter, work_dir: Path, sources: list,
                    doc_cache: dict, inactive_index: dict):
    """Resolve a ticker in priority order: (1) text embedded in the
    primary document itself (best-effort, measured rare -- see
    SYMBOL_PATTERN's docstring), (2) a name-matched CANDIDATE from Alpaca's
    inactive US-equity assets (normalized-company-name match against
    Alpaca's own inactive-asset list -- this is a candidate match, not a
    confirmed identity link: two unrelated issuers can normalize to the
    same name, and Alpaca's "inactive" status is not itself proof the
    match is the same security that filed this delisting), (3) the filer's
    *current* data.sec.gov submissions tickers, a last resort flagged
    `ticker_reuse_risk` because it is not a point-in-time record at all
    (the inactive-asset candidate is closer to point-in-time but is still
    not flagged as an identity match). Returns (ticker_or_None, method)."""
    text = record.get("_document_text")
    if text is None:
        text = fetch_primary_document(record, headers, limiter, work_dir, sources, doc_cache)
    symbol = extract_symbol_from_text(text) if text else ""
    if symbol:
        return symbol, "25-nse-primary-document"

    normalized = normalize_company_name(record["company"])
    candidates = inactive_index.get(normalized) if inactive_index else None
    if candidates:
        return candidates[0], "inactive-asset-match"

    cik = record["cik"]
    url = SUBMISSIONS_PATH.format(cik=cik)
    cache_path = work_dir / "submissions" / f"CIK{cik:010d}.json"
    try:
        raw = fetch_cached(url, cache_path, headers, limiter, sources)
        data = json.loads(raw.decode("utf-8"))
        tickers = data.get("tickers") or []
        if tickers:
            return tickers[0], "submissions-tickers"
    except (RuntimeError, json.JSONDecodeError):
        pass
    return None, "unresolved"


def run_sample_probe(common_equity_records: list, sample_size: int, seed: int, headers: dict, limiter: RateLimiter,
                      work_dir: Path, sources: list, use_alpaca: bool, doc_cache: dict) -> dict:
    rng = random.Random(seed)
    population = list(common_equity_records)
    sample = rng.sample(population, min(sample_size, len(population)))

    alpaca_module = None
    inactive_index = {}
    if use_alpaca:
        clients = build_alpaca_clients()
        alpaca_module = {"client": clients["data_client"], "request_cls": clients["request_cls"],
                          "timeframe": clients["timeframe"]}
        inactive_index = clients["inactive_index"]

    results = []
    resolved = 0
    method_counts = Counter()
    coverage_confirmed_count = 0
    for record in sample:
        record = dict(record)
        # Reuse the primary document already fetched during classification
        # when available, to avoid a second SEC request for the same file.
        record["_document_text"] = doc_cache.get(record["accession"])
        ticker, method = resolve_ticker(record, headers, limiter, work_dir, sources, doc_cache, inactive_index)
        entry = {
            "cik": record["cik"],
            "company": record["company"],
            "date_filed": record["date_filed"],
            "form": record["form"],
            "security_class": record.get("security_class"),
            "ticker": ticker,
            "resolution_method": method,
            "ticker_reuse_risk": (method == "submissions-tickers") if ticker else None,
        }
        if ticker:
            resolved += 1
            method_counts[method] += 1
            if alpaca_module is not None:
                try:
                    probe = probe_alpaca_bars(ticker, record["date_filed"], alpaca_module)
                    entry.update(probe)
                    if probe["coverage_confirmed"]:
                        coverage_confirmed_count += 1
                except Exception as exc:
                    entry["alpaca_error"] = f"{type(exc).__name__}: {exc}"
        results.append(entry)

    n = len(sample)
    return {
        "sample_size_requested": sample_size,
        "sample_size_used": n,
        "seed": seed,
        "drawn_from": "common_ordinary_equity_classified_subset",
        "ticker_resolution_rate": (resolved / n) if n else 0.0,
        "unresolved_fraction": ((n - resolved) / n) if n else 0.0,
        "resolution_method_counts": dict(method_counts),
        "alpaca_bars_checked": use_alpaca,
        "alpaca_inactive_asset_count": inactive_index and sum(len(v) for v in inactive_index.values()) or 0,
        "coverage_confirmed_rate": (coverage_confirmed_count / resolved) if (use_alpaca and resolved) else None,
        "events": results,
    }


def build_receipt(base_deduped: list, amendments: list, sources: list, probe: dict, start_year: int, start_q: int,
                   end_year: int, end_q: int, raw_count: int, duplicate_count: int,
                   classification: dict, dedupe_fallback_stats: dict, reclass_diff: dict,
                   extraction_method_counts: dict, artifact_path) -> dict:
    all_for_counts = base_deduped + amendments
    confirmed_n = sum(1 for e in probe.get("events", []) if e.get("coverage_confirmed"))
    resolved_n = sum(1 for e in probe.get("events", []) if e.get("ticker"))
    if confirmed_n > 0:
        bars_claim = (f"{confirmed_n}/{resolved_n} resolved sampled events had Alpaca SIP daily-bar "
                       "coverage confirmed to exist before the filing and stop within 10 trading days after it.")
    elif resolved_n > 0:
        bars_claim = (f"0/{resolved_n} resolved sampled events had bar coverage confirmed to stop near "
                       "the filing date (checked, not confirmed for any of them).")
    else:
        bars_claim = "No sampled events resolved a ticker, so no bar-coverage check ran."
    return {
        "id": "pre-2020-delisting-coverage",
        "kind": "delisting_coverage_index",
        "evidence_class": "open_regulator_source_measured",
        "claim": (
            "SEC EDGAR quarterly full-index Form 25 / 25-NSE (exchange "
            "deregistration) filings, deduped per filing (accession number) "
            f"for {start_year}Q{start_q} through {end_year}Q{end_q}, with amendments "
            "counted separately; Form 25-NSE primary documents classified by "
            "security class (with residual misclassification risk -- see "
            "`equity_classification` and `limitations`, not an exhaustive "
            "ground truth), common/ordinary-equity rows reported as the "
            "headline count; and a seeded sample of common-equity events "
            f"probed for ticker resolution. {bars_claim}"
        ),
        "method": (
            "Fetched https://www.sec.gov/Archives/edgar/full-index/<YEAR>/QTR<N>/form.idx "
            "for each quarter, parsed rows with a regex tolerant of per-quarter column "
            "padding, filtered to form types 25, 25-NSE and their /A amendments, deduped "
            "per accession number (not per CIK; a name-based exchange-filer fallback is used "
            "when the accession's filer-CIK prefix does not isolate a row -- see "
            "`counts.dedupe_fallback`). Every 25-NSE primary document in scope was fetched "
            "and classified into common/ordinary equity, preferred, debt, fund/ETF, "
            "warrant/right/unit or other/unknown by ordered keyword rules on the extracted "
            "security description (warrants/rights/units/preferred checked before common "
            "equity; fund-style beneficial-interest shares checked before common equity -- "
            "see `classify_security`'s docstring in collect.py for the full rule and why). "
            "Per-document classifications (accession, CIK, company, class, matched rule, "
            "description hash) are persisted to the companion artifact referenced below. "
            "From the common/ordinary-equity subset, a seeded random sample was probed: "
            "ticker resolution in priority order (primary-document text, an Alpaca "
            "inactive-asset name-matched CANDIDATE -- not a confirmed identity match -- then "
            "current data.sec.gov submissions tickers) and, when Alpaca credentials were "
            "supplied, read-only Alpaca SIP daily-bar existence in the 60 days before the "
            "filing date and whether bars stop within 10 trading days after it."
        ),
        "sources": sources,
        "counts": {
            "raw_filing_rows_before_dedupe": raw_count,
            "duplicate_accessions_removed": duplicate_count,
            "deduped_base_filings": len(base_deduped),
            "amendments": len(amendments),
            "total_index_rows": len(all_for_counts),
            "by_year_form": counts_by_year_form(all_for_counts),
            "distinct_ciks_by_year": distinct_ciks_by_year(base_deduped),
            "dedupe_fallback": dedupe_fallback_stats,
        },
        "equity_classification": {
            **classification,
            "artifact_path": str(artifact_path),
            "description_extraction_method_counts": extraction_method_counts,
            "reclassification_from_round2": reclass_diff,
        },
        "sample_probe": probe,
        "limitations": [
            "Form 25 / 25-NSE covers exchange-initiated deregistration of a class "
            "of securities under Section 12(b); it does not cover every symbol "
            "that stopped trading (e.g. OTC drops, bankruptcy delistings reported "
            "only via other filings, or plain ticker/name changes without "
            "deregistration).",
            "Dedup is per accession number (one row per filing); a CIK filing "
            "more than one deregistration in the window is counted once per "
            "filing, not collapsed to a single row. A small number of duplicate "
            "groups (see `counts.dedupe_fallback`) needed a name-based exchange-filer "
            "fallback because the accession's filer-CIK prefix did not isolate a row.",
            "Security-class classification uses ordered keyword rules on an extracted "
            "description; it is NOT an exhaustive or verified ground truth. Every "
            "document in scope was classified (not sampled), but the rules are "
            "keyword-based and residual misclassification is expected -- see "
            "`equity_classification.reclassification_from_round2` for the count of "
            "documents whose class changed between the round-2 and round-3 rules, "
            "which is itself evidence that further rule refinement could move more "
            "rows. Fund-style issuers organized as trusts (e.g. some REITs use "
            "\"shares of beneficial interest\" for ordinary common equity, not a "
            "fund/ETF unit) are a known source of possible over-classification into "
            "fund_etf under the round-3 beneficial-interest rule.",
            "Ticker resolution is not point-in-time for the submissions-tickers "
            "method (the filer's *current* known symbols), so any ticker resolved "
            "that way is flagged `ticker_reuse_risk`. The inactive-asset-match "
            "method is a normalized-company-name CANDIDATE match against Alpaca's "
            "own inactive-asset list, not a confirmed identity link; it can still "
            "mismatch on companies with similar normalized names or match a "
            "different, unrelated inactive security.",
            "Alpaca bar coverage was checked only for the sampled common-equity "
            "events, only for the 60 days before the filing date (existence) "
            "and 45 days after (stop-confirmation), only on `feed=sip`. The "
            "post-filing trading-day count uses a weekday-only approximation with "
            "no exchange-holiday calendar, which OVER-counts true trading days "
            "(holidays are weekdays with no trading), biasing "
            "`bars_continue_after_delisting` toward firing more readily, not less.",
            "2020Q1 is included only when requested, to catch filings whose "
            "effective delisting date fell in late 2019; those rows are still "
            "counted under 2020 in `counts.by_year_form`.",
            "`fetched_at` on a source entry is the original network-fetch time; "
            "on a cache hit it is read from that fetch's persisted metadata, or "
            "\"unknown\" if no such metadata exists (e.g. cached by a run before "
            "this provenance fix). `cache_read_at` marks when this run read the "
            "cached bytes and is only set on a cache hit; a cache read is never "
            "presented as a new fetch.",
        ],
        "observed_utc": utc_now(),
    }


def load_headers() -> dict:
    user_agent = os.environ.get("SEC_USER_AGENT") or os.environ.get("EDGAR_IDENTITY")
    if not user_agent:
        raise SystemExit("SEC_USER_AGENT (or EDGAR_IDENTITY) must be set in the environment")
    # Only gzip is decoded (see http_get); request gzip only so a deflate
    # response is never silently mishandled.
    return {"User-Agent": user_agent, "Accept-Encoding": "gzip"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, default=2016)
    parser.add_argument("--start-quarter", type=int, default=1)
    parser.add_argument("--end-year", type=int, default=2019)
    parser.add_argument("--end-quarter", type=int, default=4)
    parser.add_argument("--include-2020q1", action="store_true",
                         help="Also fetch 2020Q1 to catch filings for late-2019 effective dates")
    parser.add_argument("--work-dir", type=Path, default=Path("/tmp/claude-1000/delisting-work"))
    parser.add_argument("--classify-sample-2016-2018", action="store_true",
                         help="Classify all 2019 plus a seeded 400-document sample of 2016-2018 "
                              "instead of every 25-NSE document (use if the full pass is too slow)")
    parser.add_argument("--classify-seed", type=int, default=20260922)
    parser.add_argument("--sample-size", type=int, default=40)
    parser.add_argument("--seed", type=int, default=20260922)
    parser.add_argument("--use-alpaca", action="store_true", default=True)
    parser.add_argument("--no-alpaca", dest="use_alpaca", action="store_false")
    parser.add_argument("--receipt-out", type=Path,
                         default=Path("evidence/receipts/pre-2020-delisting-coverage.json"))
    parser.add_argument("--artifact-out", type=Path,
                         default=Path("evidence/artifacts/pre-2020-delisting/classifications-2016-2019.json"))
    args = parser.parse_args(argv)

    headers = load_headers()
    limiter = RateLimiter(MAX_REQUESTS_PER_SECOND)
    sources = []
    doc_cache = {}

    end_year, end_q = args.end_year, args.end_quarter
    records, index_sources = collect_index(args.start_year, args.start_quarter, end_year, end_q,
                                            args.work_dir, headers, limiter)
    sources.extend(index_sources)
    if args.include_2020q1:
        extra, extra_sources = collect_index(2020, 1, 2020, 1, args.work_dir, headers, limiter)
        records.extend(extra)
        sources.extend(extra_sources)
        end_year, end_q = 2020, 1

    base_deduped, amendments, raw_count, duplicate_count, dedupe_fallback_stats = dedupe_by_accession(records)

    nse_records = [r for r in base_deduped if r["form"] == "25-NSE"]
    targets, method, population_by_year, sampled_counts = select_classification_targets(
        nse_records, args.classify_seed, args.classify_sample_2016_2018)
    classified = classify_nse_filings(targets, headers, limiter, args.work_dir, sources, doc_cache)
    class_counts = class_counts_by_year(classified)
    reclass_diff = reclassification_diff(classified)
    extraction_method_counts = dict(Counter(r["description_extraction_method"] for r in classified))
    write_classification_artifact(classified, args.artifact_out)

    common_equity = [r for r in classified if r["security_class"] == "common_ordinary_equity"]
    common_equity_by_year = Counter(r["date_filed"][:4] for r in common_equity)
    headline_common_equity_by_year = {}
    for year, population in population_by_year.items():
        sampled_n = sampled_counts.get(year, population)
        measured = common_equity_by_year.get(year, 0)
        if method == "full_classification" or year == "2019":
            headline_common_equity_by_year[year] = {
                "measured_count": measured,
                "basis": "full_pass_with_residual_misclassification_risk",
            }
        else:
            rate = (measured / sampled_n) if sampled_n else 0.0
            headline_common_equity_by_year[year] = {
                "measured_count_in_sample": measured,
                "sample_size": sampled_n,
                "nse_population": population,
                "estimated_common_equity_count": round(rate * population),
                "basis": "estimated_from_seeded_sample",
            }

    classification = {
        "scope": "Form 25-NSE only (plain Form 25 issuer filings are not classified)",
        "method": method,
        "classify_seed": args.classify_seed,
        "documents_classified": len(classified),
        "nse_population_by_year": population_by_year,
        "sampled_counts_by_year": sampled_counts,
        "class_counts_by_year": class_counts,
        "common_ordinary_equity_by_year": headline_common_equity_by_year,
    }

    probe = run_sample_probe(common_equity, args.sample_size, args.seed, headers, limiter, args.work_dir, sources,
                              args.use_alpaca, doc_cache)
    receipt = build_receipt(base_deduped, amendments, sources, probe, args.start_year, args.start_quarter,
                             end_year, end_q, raw_count, duplicate_count, classification, dedupe_fallback_stats,
                             reclass_diff, extraction_method_counts, args.artifact_out)

    args.receipt_out.parent.mkdir(parents=True, exist_ok=True)
    args.receipt_out.write_text(json.dumps(receipt, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(f"wrote {args.receipt_out} ({len(base_deduped)} deduped filings, {len(amendments)} amendments, "
          f"{len(classified)} classified, {len(common_equity)} common-equity, {len(sources)} sources); "
          f"artifact {args.artifact_out}; reclassified {reclass_diff['documents_moved']} of "
          f"{reclass_diff['documents_compared']}; dedupe fallback used for "
          f"{dedupe_fallback_stats['groups_using_name_fallback']} groups")
    return 0


if __name__ == "__main__":
    sys.exit(main())
