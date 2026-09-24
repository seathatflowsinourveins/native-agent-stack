# Gap wave 2: us-equities / market-data-reference (2026-09-23)

Ten open gaps from the crosswalk (main `92bb279`, PR #85) were checked on this host.
Preregistrations were written at `2026-09-23T04:22:33Z` and committed in `c6846f1`
before any check ran. Receipts, raw outputs and helpers were then added.
`results.json` is generated from the receipt files by
`blueprints/gap-wave2-20260923/us-equities__market-data-reference/make_receipts.py`.

| Gap | Outcome | Evidence class | Receipt | What remains |
| --- | --- | --- | --- | --- |
| 1 | advanced | source_review | `1-ca-currency-field.json` | Fresh credentialed AAPL capture (owner: sota-workflow-resolution); coordinator adds the USD-assumption text below to the catalog |
| 4 | settled | local_integration | `4-alpaca-py-latest-seams.json` | The version pin guards against future releases |
| 5 | advanced | local_integration | `5-parameterized-comparator.json` | Promote `compare_multi.py` into the authenticated-data blueprint; exercise a real Databento or Massive export |
| 6 | advanced | native_proven | `6-us-venue-calendars-extended-hours.json` | Security-specific halts; Nasdaq and Cboe published schedules outside 2026 (NYSE markets now 2016-2028, fix round 3) |
| 7 | advanced | source_review | `7-data-licensing-clauses.json` | Account-specific Alpaca data plan and subscriber status (owner: sota-workflow-resolution); AlgoSeek/QuantQuote vendor terms and QuantConnect's login-gated data agreement for the LEAN sample |
| 8 | advanced | local_integration | `8-feast-pit-join.json` | Alpaca news (owner: sota-workflow-resolution); macro vintages, streaming ingestion, server store |
| 12 | advanced | source_review | `12-ca-currency-shared-capture.json` | Same as gap 1 |
| 14 | advanced | native_proven | `14-adhoc-closures-nyse-corroboration.json` | Security-specific halts; Nasdaq/Cboe notices for the two ad-hoc closures and their schedules outside 2026 (ICE notices and NYSE 2016-2028 tables added in fix round 3) |
| 17 | advanced | source_review | `17-sec-api-python-disposition.json` | Disposition drafted in the receipt; the ledger write (coordinator) is the open arm |
| 18 | advanced | source_review | `18-rossod4-quantlab-disposition.json` | Disposition drafted in the receipt; the ledger write (coordinator) is the open arm |

## Findings

- **Dividend currency (gaps 1 and 12).** Alpaca's current REST contract lists `currency` as
  an optional cash-dividend property. Per that contract, an empty value "can mean USD,
  non-applicable ... or unknown". The retained 2026-09-20 capture has no `currency` key,
  and alpaca-py 0.44.0 does not model the field. A key scanner found no `currency` key in
  the capture. The same scanner does find the key in the documentation's own example,
  which shows it would detect the key if present. Proposed catalog text for the coordinator:
  *"Alpaca cash_dividends.currency is optional; an absent or empty value means USD,
  not-applicable or unknown per the REST contract. Treat absent currency on a US-listed
  (foreign=false) cash dividend as USD for reconciliation. Record the row as
  currency_assumed_usd and keep it distinct from provider-stated USD."*
- **alpaca-py seams (gap 4).** The latest PyPI release is the pinned 0.44.0. Upstream
  master HEAD `232179c` differs from 0.44.0 only in `alpaca/__init__.py`. On both, the
  `_session` seam is a `requests.Session`, the `_retry` seam exists, and all 23 collector
  tests pass: unchanged on 0.44.0, and on master once the version pin is lifted. The
  unchanged suite on master fails on the version pin as designed. A mutant copy without
  `_retry = 0` fails the single-attempt test.
- **Comparator (gap 5).** `compare_multi.py` compares a reference against a provider for
  any symbols and session range. It supports five source types: a private Alpaca run, the
  broad-market Alpaca parquet, a normalized CSV, the LEAN probe and LEAN daily zips. On
  the AAPL 25-session inputs, its result is identical to the original `compare.py` output.
  It also scores IBM and SPY. Over 2016-2021, LEAN's bundled closes differ from Alpaca SIP
  closes on 43 of 1320 AAPL sessions, 211 of 1320 IBM sessions and 1214 of 1320 SPY
  sessions. This comparison does not explain those differences.
- **Calendars (gaps 6 and 14).** exchange_calendars XNYS and pandas_market_calendars NYSE
  agree exactly for 2016-2027, including open and close times and early closes. **The other
  venue names are aliases:** in both libraries XNAS, ARCX, XASE, NASDAQ and BATS resolve to
  the same NYSE rule set (`XNYSExchangeCalendar` / `NYSEExchangeCalendar`), so the five
  "venue pairs" are one comparison repeated and say nothing independent about Nasdaq, Arca,
  American or Cboe. Per-venue evidence comes from each operator's own page (fix rounds 2 and 3):
  Nasdaq's 2026 schedule (nasdaqtrader.com) and Cboe's 2026 equities schedule match the
  libraries exactly, including the 1:00 p.m. early closes on Nasdaq's page (Cboe publishes no
  early-close time). NYSE states that "All NYSE markets observe U.S. holidays as listed
  below for 2026, 2027, and 2028", and those dates match both libraries, which covers Arca and
  American directly. Fix round 3 extends NYSE-markets corroboration back to 2016: Internet Archive
  copies of NYSE's own holiday table (snapshots from 2016, 2017, 2018, 2021, 2022 and 2024) match both
  libraries for every year 2016-2026, including 1:00 p.m. early closes, when each year is taken from
  the latest snapshot that lists it. The 2021 snapshot's 2022-2023 columns predate Juneteenth and are
  superseded by the 2022 snapshot. The ad-hoc closures 2018-12-05 and 2025-01-09 are now corroborated
  by ICE's own press releases (archived), which name the NYSE Group markets that closed. Nasdaq and
  Cboe schedules outside 2026, and their ad-hoc closures, still rest on the aliased NYSE rule set.
  pandas_market_calendars' extended hours (04:00-09:30 and 16:00-20:00, with a 17:00 close on
  early-close days) match only the venues whose early session starts at 4:00 a.m. (NYSE Arca,
  Cboe BZX/EDGX). NYSE American, National, Texas and Cboe BYX/EDGA open at 7:00 a.m. **pandas_market_calendars 5.4.0's IEX calendar is wrong:** it adds 25
  dates as sessions, including New Year's Day, Labor Day and both ad-hoc closures, so do
  not use it.
- **Licensing (gap 7).** Alpaca market data is provided for personal, non-commercial use.
  It may not be reproduced, distributed, sold or commercially exploited without Alpaca's
  written consent (Customer Agreement section 30, and the Terms and Conditions). The NYSE
  and Nasdaq subscriber agreements prohibit furnishing the data to others. None of these
  documents has an explicit clause on private local storage. SEC website information is
  public and may be copied or redistributed with citation, within the fair-access limit
  of 10 requests per second. Raw Alpaca payloads therefore stay private. The LEAN sample
  data used by the comparator (`Data/equity/usa/daily/{aapl,ibm,spy}.zip` at LEAN `985ef30`)
  is tracked in the LEAN repository, which is licensed under Apache-2.0 with no data carve-out
  or data-specific notice. Its equity readme names AlgoSeek and QuantQuote as the sources.
  QuantConnect's site terms restrict redistribution of Site content, but they govern the website,
  not the repository. Gap 7 stays advanced (fix round 2): the account-specific Alpaca plan terms
  and the upstream vendor terms were not read.
- **Feast (gap 8).** Feast 0.66.0's point-in-time join returned no future value, and a
  later restatement won over the original row. However, it **silently drops** an entity
  row whose only feature rows are older than the TTL. An entity with no rows at all is
  returned with a null. Anyone adopting Feast needs a left-join guard.

## Boundaries

- Fix round 3 (re-dispatched unit, 2026-09-23 13:00Z onward): `preregistration-fix-round3.json` was written
  at `13:01:09Z` and committed in `97cf2a8` before any round-3 fetch. Its addendum for the archived NYSE
  tables was written at `13:03:27Z` and committed in `4074556`, after the press releases were read but
  before any table was parsed. It is labelled as such. `archive_calendar_check.py` needed two fixes during
  the run, both disclosed in the receipts. Run 1 did not parse the 2018 table (its header row is a bare
  `<thead>`). Run 2 paired the title word "Close" with a body date about 1,600 characters later, so the
  verb-to-date distance is now capped at 200 characters. The final output is identical on the cache originals
  and on the published copies (file names and hashes excluded). The outcomes did not change: gaps 6 and 14
  stay advanced because security-specific halts, plus Nasdaq and Cboe schedules outside 2026, remain open.
  A read-only Codex review of the uncommitted round-3 diff (`raw/review-codex-round3.txt`) found no blocker
  or major issue and 2 minor ones. First, the extractor was documented as reporting every date after a
  closure verb, but it takes only the first date. Second, the holiday self-test bypassed the HTML parser.
  A review-fix preregistration (`review_fix`, written `13:18:12Z`, committed in `107cfdf`) preceded the fixes.
  The documentation now states first-date scope. The self-test now injects a table row and re-parses the page;
  a mutant with the cell parser disabled makes it report false (`raw/14-selftest-mutation.fix3.txt`).
  The rerun changed no outcome.
- EOL integrity fix (round 3, `eol_fix` preregistration written `13:25:21Z`, committed in `1240cb9`): five published
  raw HTML files were CRLF in the worktree, but git stores them as LF (`* text=auto eol=lf`). Two of them are
  round-2 files (`6-nasdaqtrader-holiday-calendar.html`, `7-quantconnect-terms.html`), so their recorded hashes
  would not have matched a fresh checkout. `eol_normalize.py` rewrote all five as LF, and each worktree hash now
  equals its git blob hash. The ledger entries in `raw/REDACTIONS.json` keep the CRLF hashes. Reruns of
  `venue_pages_check.py`, `lean_rights.py` and `archive_calendar_check.py` on the LF copies give results
  identical to the committed ones (`raw/*.eolfix3.json`).
- Guarded gitleaks flagged the two archived ICE press-release pages (4 `generic-api-key` findings: the
  ir.theice.com site's embedded public Q4 API key). They are therefore published only as tag-stripped text
  (`raw/14-wayback-ice-*.txt`, produced by `ice_text_publish.py`). The Bush text also has Business Wire's
  `/home/<id>` URL path redacted, following `publish_raw.py`'s rule, because `scripts/validate.py` rejects that shape. The original HTML hashes are in
  `raw/REDACTIONS.json`, and the full pages stay in the cache directory. The press-arm results are identical
  on the text copies. These pages were never committed as HTML. A second guarded scan of the whole layer
  evidence and helper directories found 0 findings (`raw/gitleaks-round3-summary.fix3.json`).
- Fix round 2 (independent Opus review of `fe8b66e`): a preregistration
  (`preregistration-fix-round2.json`, written `2026-09-23T04:58:07Z`, committed in `5f248b6`)
  preceded the new fetches and checks. Gap 7 changed from settled to advanced, and gaps 17
  and 18 changed from settled to advanced. Gap 1 uses the same standard: a ledger or catalog
  write that this unit may not perform leaves that arm open. The calendar venue aliasing is
  now disclosed.
- **Integration condition: squash-merge only.** Commit `dfcfa51` added nine gzip raw files
  that later commits removed. The guarded gitleaks history scan does not decode gzip. To
  cover that gap, the nine blobs were decompressed into a scratch directory and scanned with
  guarded gitleaks (`raw/history-gz-gitleaks-summary.fix2.json`). The result was 21 findings,
  all in the third-party Alpaca docs page: pagination `next_page_token` examples, the docs
  site's public search `apiKey`, its public reCAPTCHA site key and an httpbin.org bearer
  example. The other eight blobs had no findings. Secret values are not recorded. A squash
  merge keeps `dfcfa51` out of main.

- No Alpaca or broker request, paper-account call or credential read was made. Those arms
  are deferred to sota-workflow-resolution. Private Alpaca files from 2026-09-20 were read
  on this host, and only key names, counts and hashes were published.
- Network downloads (all disclosed):
  - Alpaca docs, the NYSE page, Alpaca disclosure PDFs and Internet Archive SEC snapshots.
  - Fix round 3: Internet Archive CDX queries and `id_` snapshots of nyse.com/markets/hours-calendars
    (10 snapshots, 6 used) and of two ir.theice.com press releases (3 copies, 2 used), about 1.4 MB in total.
  - Fix round 2: nasdaqtrader.com holiday calendar, nasdaq.com holiday page, cboe.com hours page
    (and its 404 US-equities URL), and quantconnect.com/terms (the data-terms URL redirected to login).
  - GitHub API GETs and PyPI JSON.
  - uv packages: 562 MB of cache, mostly Feast's dependency tree. These were installed
    through `ecosystem-bounded-run` into `$HOME/.cache/gap-wave2-20260923/market-data-reference/`.
- No service, port, systemd unit or live store was touched.
- Independent review: I requested one read-only Codex review (`raw/review-codex-round1.txt`).
  The first invocation stalled reading stdin and was stopped without output; the second
  completed. It reported 5 defects in the helpers for gaps 5, 6, 8 and 14. After those
  findings, I wrote a fix-round preregistration (`preregistration-fix-round1.json`,
  04:41:56Z), fixed all 5 defects and re-ran the checks (`raw/*.fix1.*`). The outcomes did
  not change, and each fix has a self-test that detects the defect class it closes.
- After the runs, the three shell helpers' default worktree path was changed from a
  hard-coded host path to a script-relative path (`$(dirname "$0")/../../..`). This is
  the same directory on this host, and no other logic changed.
- Third-party downloads are stored as plain UTF-8, with UUID-shaped tokens replaced by
  `<uuid-redacted>`. These tokens are page, element and release identifiers, not local
  session IDs. They were redacted because `scripts/validate.py` rejects UUID-shaped
  strings and only inspects UTF-8 text. `raw/REDACTIONS.json` records each file's
  original sha256 and redaction count, and `publish_raw.py` performs the conversion.
  In fix round 2, two third-party URL paths shaped like a home directory (slash-home-slash-`index.jsp`
  links on the nasdaqtrader page) were redacted the same way, because `scripts/validate.py`
  rejects that shape. The page's holiday table is unaffected.
- The full Alpaca corporate-actions docs page is not published. It embeds public site keys
  (search and reCAPTCHA) and example tokens that gitleaks flags. Only its schema fragments
  are published, in `raw/1-alpaca-corporateactions-docs.excerpt.json`, together with the
  page sha256 (`ee3a3fbb...`). The full page stays in the cache directory.

## Coordinator note (2026-09-23): CodeQL fixes

CodeQL flagged the HTML stripping in `archive_calendar_check.py` and `calendar_check.py` (py/bad-tag-filter). Both now strip `<script>` and `<style>` blocks case-insensitively and accept end tags such as `</script >`. Applied to all 13 retained `raw/*.html` inputs, the old and new expressions give byte-identical text, so no receipt changes. Neither script's hash is pinned by a receipt.
