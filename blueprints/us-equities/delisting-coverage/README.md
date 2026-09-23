# Pre-2020 delisting coverage from SEC EDGAR

This blueprint answers one gate: `pre-2020-delisting` in
`catalogs/us-equities/gates-20260922.json` ("Delisting coverage before 2020
from an entitled or open dated source"). Context:
`blueprints/us-equities/broad-universe/README.md` measured 25/47/167
delisted-by-last-bar symbols in 2016/2017/2018 against 541-756 per year in
2021-2025 (no candidate discovered a market-wide delisting list before 2020
from an entitled or open source, other than a 1-star repository). This
blueprint builds a different, narrower, first-party source instead: SEC
EDGAR's own quarterly full-index of filed forms. It is read-only and uses no
Alpaca trading endpoint (only historical data and read-only asset lookups).

## What it does

1. Fetches `https://www.sec.gov/Archives/edgar/full-index/<YEAR>/QTR<N>/form.idx`
   for 2016Q1 through 2019Q4 (one HTTPS GET per quarter, under 5 requests/second,
   `SEC_USER_AGENT` sourced from an operator-provided env file outside the repo,
   never printed). A quarter file that fails to parse or yields zero
   delisting-form rows raises rather than silently returning an empty result.
2. Parses every row with a regex tolerant of the per-quarter column-width
   variation SEC's fixed-width generator produces, not a hardcoded byte offset.
3. Filters to form types `25`, `25-NSE` and their `/A` amendments — the forms
   an exchange files under Section 12(b) to deregister a class of securities.
   This is exchange-initiated deregistration, **not** every symbol that
   stopped trading (OTC drops, bankruptcy delistings reported via other
   forms, or a plain ticker/name change are out of scope).
4. Dedupes **per filing (accession number)**, not per CIK. Every Form 25-NSE
   accession is cross-listed in the index twice — once under the delisted
   issuer's CIK, once under the filing exchange's own CIK — so dedup keeps
   the issuer's row using the accession's filer-CIK prefix. When no row's
   CIK matches that prefix at all (measured: 70 of the duplicate groups in
   the full 2016-2019 run), it falls back to identifying the exchange row by
   name (NYSE, Nasdaq, Cboe, IEX, etc.) and keeps the other row; this
   name-based fallback changed the pick (versus taking the first row
   arbitrarily) for 22 of those 70 groups.
5. Classifies every Form 25-NSE's primary document by security class
   (common/ordinary equity, preferred, debt, fund/ETF, warrant/right/unit,
   other/unknown) using ordered keyword rules: fund/ETF keywords, then a
   fund-style-issuer "beneficial interest" rule, then debt, then
   **warrant/right/unit and preferred/preference keywords — checked before
   common equity**, then common-equity keywords last. This order exists
   because two classes of documents contain the literal substring "common
   stock" while not being common equity: a shareholder-rights ("poison
   pill") plan is commonly titled "Common Stock Purchase Rights", and a
   fund/trust's "Common Shares of Beneficial Interest" is a fund/ETF unit.
   **Headline counts are the common/ordinary-equity rows only**; other
   classes are reported per year, never folded into the headline. Every
   in-scope document (all 3,181 Form 25-NSE filings, 2016-2019) was
   classified in this run — this is a full pass, **not a verified or
   exhaustive ground truth**: the rules are keyword-based, residual
   misclassification is expected, and 261/3,181 documents changed class
   between the previous rule order and this one (see
   `equity_classification.reclassification_from_round2` in the receipt).
   Per-document classifications (accession, CIK, company, class, matched
   rule, description hash) are persisted to
   `evidence/artifacts/pre-2020-delisting/classifications-2016-2019.json`,
   referenced from the receipt, so the audit trail does not depend on a
   local work directory.
6. Draws a seeded sample from the common/ordinary-equity subset only (not
   the full index) and, for each event, resolves a ticker in priority order:
   text embedded in the primary document itself (measured zero yield across
   3,181 documents — the modern XML schema never carries a trading-symbol
   field), a normalized-company-name **CANDIDATE** match against Alpaca's
   inactive US-equity assets (this is a candidate match, not a confirmed
   identity link — two unrelated issuers can normalize to the same name),
   then the filer's *current* data.sec.gov submissions tickers as a last
   resort (flagged `ticker_reuse_risk` since it is not point-in-time at all).
7. For each resolved ticker, checks read-only whether Alpaca SIP daily bars
   exist in the 60 days before the filing date **and stop within 10 trading
   days after it**. Bars found to continue well past the filing are flagged
   (`bars_continue_after_delisting`) and never counted as coverage
   (`coverage_confirmed`).
8. Writes `evidence/receipts/pre-2020-delisting-coverage.json` with every
   fetched source's URL/sha256/bytes, per-year/per-form counts, the equity
   classification (with the artifact reference and reclassification diff),
   and the sample-probe results. A source's `fetched_at` is the *original*
   network-fetch time, persisted in a cache sidecar; a cache hit sets
   `cache_read_at` separately and is never presented as a new fetch. If no
   sidecar exists for an older cached file, `fetched_at` is `"unknown"`.

## Run it

```
set -a
source <path to operator-provided sec.env>       # sets SEC_USER_AGENT
source <path to operator-provided alpaca paper env>  # sets APCA_API_KEY_ID / APCA_API_SECRET_KEY
set +a
python3 blueprints/us-equities/delisting-coverage/collect.py \
  --start-year 2016 --start-quarter 1 --end-year 2019 --end-quarter 4 \
  --work-dir <scratch dir outside the repo> \
  --sample-size 40 --seed 20260922 --use-alpaca \
  --receipt-out evidence/receipts/pre-2020-delisting-coverage.json \
  --artifact-out evidence/artifacts/pre-2020-delisting/classifications-2016-2019.json
```

Raw index files and primary documents are cached under `--work-dir` (outside
the repo); rerunning with the same work dir reuses the cache instead of
refetching. Use `--include-2020q1` to also fetch 2020Q1 for filings whose
effective delisting date fell in late 2019 (those rows are still counted
under 2020 in the receipt). Use `--classify-sample-2016-2018` to classify
all of 2019 plus a seeded 400-document sample of 2016-2018 instead of every
document, if a full pass is too slow on a given host.

## Measured results (2026-09-22, 2016Q1-2019Q4, reclassified from round 2)

- 16 quarterly index files fetched, 30.5MB-48.6MB each (gzip-transparent).
  6,867 raw Form 25/25-NSE/amendment rows; 3,239 removed as duplicate
  accessions; 3,577 deduped base filings, 51 `/A` amendments.
- Per-year base-filing counts (`25` + `25-NSE`): 2016 894, 2017 848, 2018
  925, 2019 910; distinct filer CIKs per year: 691 / 641 / 639 / 672.
- **Equity-classified headline (common/ordinary equity only, Form 25-NSE,
  full pass over all 3,181 in-scope documents, NOT a verified ground
  truth)**: 2016 378, 2017 296, 2018 268, 2019 294. Against the
  broad-universe blueprint's 25/47/167 last-bar-implied 2016-2018 figures,
  the measured ratios are **15.1x (2016), 6.3x (2017), 1.6x (2018)** — this
  counts *filed deregistrations of common/ordinary equity specifically*,
  not symbols inferred from missing bars. No causal claim is made about why
  the ratio narrows toward 2018; that would require independently
  measuring the last-bar method's own coverage over time, which this
  blueprint does not do.
- Non-headline classes (2016/2017/2018/2019, for context, never included
  above): preferred 91/93/64/67, debt 116/157/166/184, fund/ETF
  91/103/147/124, warrant/right/unit 70/70/123/109, other 51/33/57/29
  (from `equity_classification.class_counts_by_year` in the receipt).
- **Reclassification from the round-2 rule order**: 261/3,181 documents
  (8.2%) moved class. Largest transitions: `other -> warrant_right_unit`
  (77, mostly rights/warrants previously falling through to "other"),
  `preferred -> warrant_right_unit` (53), `common_ordinary_equity ->
  warrant_right_unit` (51, includes the "Common Stock Purchase Rights"
  fix), `common_ordinary_equity -> fund_etf` (40, the beneficial-interest
  rule), plus smaller `-> preferred` and `-> fund_etf` transitions. All
  3,181 documents used the modern XML `descriptionClassSecurity` field for
  extraction (0 used the older free-text HTML fallback path) — no
  HTML-format Form 25-NSE documents occur in this 2016-2019 window, so
  that fallback path is untested here even though it remains in the code.
- Sample probe (n=40, seed 20260922, re-drawn from the corrected
  common-equity subset): **ticker resolution rate 2.5% (1/40)**, via
  `submissions-tickers` (current mapping, flagged `ticker_reuse_risk`); the
  Alpaca inactive-asset name-match candidate index has 18,638 entries but
  matched none of this sample's 40 companies by normalized name; 0/40
  matched the primary-document text.
- **Bars-stop check: 0/1 resolved events confirmed** (checked, not
  confirmed for the one resolved ticker — it had zero SIP bars in the
  60-day pre-window at all, so it fails on existence, not on continuation).
  The round-2 write-up's explanation for its 0/4 result ("most likely a
  different or reused security" for ROGERS CORP/`ROG` and DOVER
  MOTORSPORTS/`DVD`) was wrong: both of those round-2 sample events were
  actually **"Common Stock Purchase Rights"** filings misclassified as
  common equity by the round-2 rule order, not a different/reused-ticker
  case. The round-3 classification fix removes both from the
  common-equity population entirely, so they no longer appear in this
  sample; whether resolved tickers' bars continuing past a *correctly*
  classified common-equity delisting indicates reuse remains untested here
  because this re-drawn sample only resolved one ticker, and that one
  failed on pre-window existence rather than the stop condition.

## Limitations (also recorded in the receipt)

- Covers Section 12(b) exchange deregistration only, not every delisting.
- Dedup is per accession number (one row per filing); a CIK filing more
  than one deregistration in the window is counted once per filing. A
  small number of duplicate groups (70 of them) needed the name-based
  exchange-filer fallback described above.
- Security-class classification uses ordered keyword rules on an extracted
  description and is **not** an exhaustive or verified ground truth;
  residual misclassification is expected (see the reclassification-diff
  figures above). Fund-style issuers organized as trusts (e.g. some REITs
  use "shares of beneficial interest" for ordinary common equity, not a
  fund/ETF unit) are a known source of possible over-classification into
  `fund_etf` under the beneficial-interest rule.
- Ticker resolution is not point-in-time for the `submissions-tickers`
  method (flagged `ticker_reuse_risk`); `inactive-asset-match` is a
  name-normalization **candidate** match against Alpaca's own inactive-asset
  list, not a confirmed identity link.
- Alpaca bar coverage was checked only for the sampled common-equity
  events, only for the 60 days before (existence) and 45 days after
  (stop-confirmation) the filing date, only on `feed=sip`. The post-filing
  trading-day count is a weekday-only approximation with no exchange-holiday
  calendar, which **over-counts** true trading days (holidays are weekdays
  with no trading), biasing `bars_continue_after_delisting` toward firing
  more readily, not less.
- `fetched_at` on a source entry is the original network-fetch time,
  persisted in a cache sidecar; on a cache hit with no such sidecar (e.g.
  cached by a run before this provenance fix), it is reported as
  `"unknown"` rather than back-filled with the current time. `cache_read_at`
  marks when a run actually read cached bytes and is only set on a cache hit.

## Independent qualification (2026-09-22, three rounds)

An independent evidence review re-ran the collector's parsing, dedupe and
classification functions over the cached sources and reproduced the counts
exactly: 3,577 accession-deduped Form 25/25-NSE filings, and 378/296/268/294
common-equity rows for 2016-2019, matching the per-document artifact. The
review kept the `pre-2020-delisting` gate **not established**. The receipt is
partial evidence. Residual issues it measured in the keyword classification:

- 58 partnership/trust "common units" fall into `warrant_right_unit`, because
  the `unit` rule fires first.
- About 16 real-estate trusts with "shares of beneficial interest" are
  classified as `fund_etf`.
- About 55 common-equity rows have fund-style issuer names (for example
  municipal or income funds) and were not checked against their documents.
- 2 preference-share ADS with the misspelling "Preferrence" count as common.
- 3,177 of 3,237 sources have `fetched_at: "unknown"`, because they were cached
  before the provenance fix.

The seeded common-equity sample resolved 1/40 tickers, with 0 confirmed
price paths. Closing the gate needs a corrected equity-event list with
point-in-time ticker identity and price history through each delisting. A
dated identity source is the likely route (see the `dated-security-identity`
and `databento-arm-b` gates).
