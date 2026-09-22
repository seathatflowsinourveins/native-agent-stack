# Point-in-time news/filing availability and as-published vintage prices

Measures gate `pit-news-filings` in `catalogs/us-equities/gates-20260922.json`
("Point-in-time news/filing availability and as-published vintage prices",
receipt `evidence/receipts/pit-availability.json`). On the sample in
`plan.json` (`preregistered: false` -- the plan was revised after seeing
round-1 and round-2 results, see `plan.json` `history`; `plan_written_utc` in
the receipt is `plan.json`'s own filesystem mtime via `os.stat`, read at run
time rather than hand-written, so it cannot postdate or be fabricated ahead
of the run that produced the receipt citing it), asks what can be known
point-in-time from open (SEC) or already-entitled (Alpaca paper/SIP,
Benzinga news) sources -- not whether a complete point-in-time
reconstruction system exists.

**Survivorship**: all 20 filings/news symbols and all 5 vintage-price symbols
in `plan.json` are currently listed as of the plan's write time; none was
delisted. Two are renamed, same-CIK entities within the sample window, not
delistings: META's CIK (`data.sec.gov` `formerNames`) filed as "Facebook Inc"
from 2005 to 2021-10-27, then as "Meta Platforms, Inc." (ticker FB before,
META from June 2022); RIOT's CIK filed as "Riot Blockchain, Inc." from
2017-10-04 to 2022-12-19, then as "Riot Platforms, Inc." (ticker RIOT
unchanged throughout, per `data.sec.gov`). Neither is a ticker-to-CIK identity
break like XOM/DKNG (see Part (a)); both resolve to one continuous CIK.
Nothing measured here establishes filing, news or price availability for a
symbol that was delisted before today; the numbers below describe
currently-listed survivors only, two of which carry a mid-window rename.

| File | Role |
| --- | --- |
| `plan.json` | sample: symbols, forms, sampled news weeks, vintage-price window, `preregistered`, `history` |
| `measure.py` | parsing/classification functions (unit-tested offline) + network `run_*`/CLI |
| `../../../evidence/receipts/pit-availability.json` | the measured receipt |
| `../../../tests/test_pit_availability.py` | offline tests, no network |

## Part (a): SEC filings acceptance time and completeness

Source: `data.sec.gov/submissions/CIK{10-digit}.json` per symbol (ticker→CIK
from `www.sec.gov/files/company_tickers.json`), 20 symbols (`plan.json`
`symbols_filings_news`), forms 8-K, 8-K/A, 10-Q, 10-Q/A, 10-K, 10-K/A
(amendments counted as their own `by_form` category, not merged into the
parent form), 2016-01-01..2026-09-22. User-Agent sourced from the local SEC
contact env file (path in `$PIT_SEC_ENV_PATH`, an operator-exported env var
per `plan.json` `env_files`) into the child process only, never printed;
requests throttled to <= 5/s. `filings.recent` in the submissions JSON only
holds a symbol's most recent filings; every entry in `filings.files[]` (the
older, paginated history) is also fetched and merged for every symbol.

**Completeness check**: each symbol should carry roughly one 10-K per year
(`filings_expected_10k_per_symbol: 10`, `filings_completeness_tolerance: 2`
in `plan.json`); `check_10k_completeness()` flags `shortfall: true` when a
symbol's 10-K count (10-K/A counted separately) is more than the tolerance
below expected, and `run_filings()` also records the resolved
`sec_cik`/`sec_entity_name`/`sec_current_tickers` and every `older_files_fetched`
entry per symbol so a shortfall can be diagnosed rather than just flagged.

**Identity breaks (XOM, DKNG)**: `www.sec.gov/files/company_tickers.json`
currently maps ticker `XOM` to CIK `0002115436` ("ExxonMobil Holdings Corp",
`sec_current_tickers: ["XOM"]` -- correctly self-consistent, not `[]`), a
newly registered filer with almost no 2016-2026 history of its own (0 10-Ks)
and an empty `files[]`. The 2016-2026 10-K/10-Q history most public sources
mean by "XOM" was filed under CIK `0000034088` ("EXXON MOBIL CORP", 7 10-Ks,
20 10-Qs, 107 8-Ks), which `data.sec.gov` no longer lists a current ticker for
(`tickers: []` on *that* CIK, confirmed via `efts.sec.gov` full text search).
The same pattern was checked for DKNG: current CIK `0001883685`
("DraftKings Inc.", `tickers: ["DKNG"]`) only covers 2021-10-08 onward (4
10-Ks); the pre-2022-holdco-reorg entity (an `8-K12B` dated 2022-05-05 on the
current CIK evidences the reorg) is CIK `0001772757` ("DraftKings Holdings
Inc.", `tickers: []`, 3 10-K + 2 10-K/A, 8 10-Q + 2 10-Q/A, 49 8-K + 1 8-K/A,
2019-04-05..2024-06-17). Both are ticker-to-CIK identity breaks, not a
`files[]`-fetching bug: `run_filings()` records `identity_break` (both CIKs),
excludes the current-CIK filings from `overall` coverage
(`symbols_excluded_from_overall`) rather than counting them as representative
2016-2026 coverage, and separately probes the historical CIK
(`historical_cik_probe`, not merged into `overall` or `per_symbol` totals).

**Post-close window, per form**: filing acceptance is bucketed into three
Eastern-time sessions (`classify_acceptance_session`): `regular` (06:00-16:00,
the close-based look-ahead-risk boundary -- a strategy trading against the
16:00 close cannot see anything accepted after it), `post_close`
(16:00-17:30) and `after_hours` (>=17:30 or <06:00). `post_close_share_of_accepted`
and `after_hours_share_of_accepted` are reported both overall and per form
(each `by_form[form]` entry carries its own `regular_count`/`post_close_count`/
`after_hours_count` and shares), since the overall share mixes forms with very
different filing conventions (e.g. 8-K deadline pressure vs. scheduled 10-K/10-Q).

**Real-EDGAR fixture**: `tests/test_pit_availability.py`'s
`RealEdgarAcceptanceFixtureTests` freezes three real filings (AAPL 10-Q, MSFT
8-K, JPM 10-K) fetched live from data.sec.gov's submissions JSON and each
filing's own full-submission `.txt` header (e.g.
`https://www.sec.gov/Archives/edgar/data/320193/0000320193-26-000020.txt`),
and asserts that the JSON's UTC `acceptanceDateTime`, converted to Eastern
here, equals the header's own Eastern-local `ACCEPTANCE-DATETIME` field
(format `YYYYMMDDHHMMSS`) exactly -- confirming the UTC reading against an
independent source field rather than inferring it from the `Z` suffix alone.

**Limitation**: `acceptanceDateTime` is when SEC's system accepted the
submission, not when any downstream feed or consumer first received it.

## Part (b): News timestamp behaviour

Source: `https://data.alpaca.markets/v1beta1/news` (Benzinga content),
20 symbols, one fixed 7-day week per year 2016-2026 (`plan.json`
`news_weeks_sampled`, chosen before any content was inspected). Credentials
loaded only into the child process from the local Alpaca paper-profile env
file (path in `$PIT_ALPACA_ENV_PATH`), never printed.

**created_at query-window filter**: the endpoint's `start`/`end` parameters
were found to admit items whose `created_at` falls outside the requested
window (its date filter can match on `updated_at` instead of original
publication time). `filter_items_created_in_window()` keeps only items whose
`created_at` is actually inside the sampled week; every year's output reports
both the raw-returned summary and the `created_at`-filtered summary, plus
`created_at_outside_window_count`/`share` as direct measured evidence of how
often this happens (not asserted in prose from a single example).

**Measure name**: the timestamp comparison is called `updated_after_created`
(`updated_at` strictly later than `created_at`) throughout, not "content
revision" -- the API exposes no diff or revision history, so a timestamp
comparison is what is actually measured.

**SDK behaviour**: alpaca-py 0.44.0's `NewsClient.get_news()` *does* paginate
automatically (`BaseRestClient._get_marketdata` loops on `next_page_token`
exactly as `NewsRequest.page_token`'s docstring says). The actual mismatch is
that `NewsRequest.limit` is documented as a per-page limit but is implemented
in `alpaca/common/rest.py` as a total cap across every page
(`actual_limit = min(int(limit) - total_items, page_limit)`); passing
`limit=50` with the SDK, as an earlier version of this script did, correctly
stopped it at 50 items total, not one page -- that earlier version's claim
that the SDK "silently truncates to one page" was wrong and is withdrawn.
`measure.py` keeps direct REST for this part (same host, params and
`APCA-API-KEY-ID`/`APCA-API-SECRET-KEY` headers the SDK itself uses) with its
own `next_page_token` loop and no total-item cap, which is simpler than
tracking the SDK's documented-per-page-vs-implemented-as-total distinction
across 11 yearly requests.

## Part (c): Vintage prices (raw vs. fully adjusted)

Source: alpaca-py 0.44.0 `StockHistoricalDataClient.get_stock_bars`
(`feed="sip"`, `adjustment=RAW` and `adjustment=ALL`) and
`CorporateActionsClient.get_corporate_actions`, 5 symbols with a known 2016-2026
split (AAPL, AMZN, GOOGL, NVDA, TSLA; `plan.json`
`symbols_vintage_prices_rationale`), full 2016-01-01..2026-09-22 daily series.

**Step detector -- splits only**: `detect_ratio_step()` uses a relative,
log-space step (`|ln(ratio_t) - ln(ratio_t-1)| > 0.05`, i.e. >5% relative
change) instead of a fixed absolute tolerance. A fixed absolute tolerance is
comparable to ordinary rounding/precision noise when the ratio is near 1.0
and comparable to a real multi-way split when the ratio is 15-20+, so it
produced false positives: the previous 0.005 absolute tolerance found 155
"steps" in TSLA's raw/adjusted ratio even though TSLA pays no dividend and
the ratio only genuinely steps at its two splits. The log-relative threshold
is scale-invariant across both regimes, but by design it covers **splits
only**: an ordinary ex-dividend adjustment factor is typically ~0.1-1%, well
below the 5% threshold, so this detector does not and is not intended to
catch dividend-driven ratio changes.

**Matched vs. unmatched steps**: every detected step date is matched against
the corporate-actions endpoint's own `ex_date`/`process_date`/`payable_date`/
`record_date` records (`match_steps_to_corporate_actions()`) within
`vintage_prices_window_days_around_action` (`plan.json`, currently used as
the match window rather than dropped) calendar days; `steps_matched_to_corporate_action`
and `steps_unmatched` are reported per symbol so an unmatched step is visible
as either detector noise or a real adjustment the sampled corporate-actions
window didn't carry a matching date for.

**Separate dividend check**: `detect_dividend_adjustment()` compares, for
each `cash_dividends` record's `ex_date`/`rate`, the observed raw/adjusted
log-step on that date against the expected magnitude
`|ln(close) - ln(close - rate)|` (raw close on the nearest prior trading
date), with its own `+-50%` relative tolerance (`DIVIDEND_STEP_TOLERANCE_RATIO`)
-- independent of the 5% split threshold above. Reported per symbol as
`dividend_adjustment_check` (`records_checked`/`matched_count`/`unmatched_count`).

**What this establishes**: `adjustment=raw` bars are unadjusted for later
corporate actions (the discontinuity is visible and, where matched, lines up
with the independently-listed corporate-action dates); `adjustment=all` bars
are adjusted, consistent with the corporate-actions record.

**What this does NOT establish**: Alpaca's raw daily bars are *as currently
served*, not a versioned record of what was originally printed intraday --
there is no endpoint here that returns a prior version of a bar before a
later trade correction or busted-trade adjustment. Nothing measured here
proves the absence of same-day revisions to a raw print; it only shows the
corporate-action-driven adjustment gap between the two `adjustment` modes.

## Running

Export the operator-local env vars named in `plan.json` `env_files` first
(`$PIT_SEC_ENV_PATH`, `$PIT_ALPACA_ENV_PATH`, and `$PIT_ALPACA_PYTHON` for the
pinned alpaca-py 0.44.0 interpreter); no literal path is committed here (see
`scripts/validate.py` `PRIVATE_CONTENT`).

```sh
python3 -m unittest tests.test_pit_availability   # offline, no network
"$PIT_ALPACA_PYTHON" blueprints/us-equities/pit-availability/measure.py \
  --parts filings,news,prices
```

The SEC part also runs fine under plain `python3` (stdlib `urllib` only); the
news/prices parts need the pinned alpaca-py 0.44.0 environment.
