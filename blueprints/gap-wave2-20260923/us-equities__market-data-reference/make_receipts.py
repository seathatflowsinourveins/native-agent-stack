#!/usr/bin/env python3
"""Write the layer's gap receipts from RECEIPTS below, then results.json from the receipts.

Usage: python3 make_receipts.py UNITS_JSON
gap_text_sha256 is computed from the unit's gap text; preregistration comes from the committed
preregistration.json; raw artifact hashes are computed from the files on disk (a missing file fails).
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EV = Path("evidence/artifacts/gap-wave2-20260923/us-equities__market-data-reference")
BP = "blueprints/gap-wave2-20260923/us-equities__market-data-reference"
CACHE = "$HOME/.cache/gap-wave2-20260923/market-data-reference"
PRIVATE_RUN = "$HOME/codex-ecosystem/state/authenticated-data-20260920/alpaca-run-1"


def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def raw(*names):
    return [{"path": str(EV / "raw" / n), "sha256": sha(EV / "raw" / n)} for n in names]


RECEIPTS = {
 1: {"slug": "ca-currency-field", "outcome": "advanced", "evidence_class": "source_review",
     "checked_at": "2026-09-23T04:24:19Z",
     "commands": [
        f"curl -sSL -o {CACHE}/docs/ca-docs.html https://docs.alpaca.markets/us/reference/corporateactions-1",
        f"{CACHE}/alpaca-latest/bin/python {BP}/ca_currency_probe.py {CACHE}/docs/ca-docs.html {PRIVATE_RUN} > {EV}/raw/1-ca-currency-probe.json",
        f"python3 {BP}/docs_excerpt.py {CACHE}/docs/ca-docs.html > {EV}/raw/1-alpaca-corporateactions-docs.excerpt.json   # publication step; full page withheld (gitleaks flagged its public site keys and example tokens)"],
     "results": [
        "docs HTTP 200, 989491 bytes; REST schema cash_dividend.properties includes 'currency' ($ref #/components/schemas/currency); required = [id, symbol, cusip, rate, special, foreign, process_date, ex_date] (currency NOT required)",
        "components.schemas.currency.description: \"The ISO 4217 currency code associated with the corporate action.\\nEmpty value can mean USD, non-applicable (e.g. for name changes) or unknown\\n(can change later to a valid currency).\"",
        "alpaca-py 0.44.0 (latest PyPI) CashDividend fields: id, corporate_action_type, symbol, cusip, rate, special, foreign, process_date, ex_date, record_date, payable_date, due_bill_on_date, due_bill_off_date -> currency_field false",
        "retained 2026-09-20 private capture: actions-001.json (cash_dividends) currency_key_present=false; actions-002.json (forward_splits) currency_key_present=false (key paths only, no values)",
        "positive control: the same key scanner finds 'currency' in the docs' own SSE CashDividend example -> true"],
     "detection": "Recursive key-path scan lists every key in each body; its positive control on the docs SSE example (which carries currency=USD) returned true, so a present currency key would have been reported.",
     "limits": [
        "No fresh credentialed AAPL corporate-actions request: credential reads and Alpaca/broker contact belong to peer session sota-workflow-resolution (brief hard rule). That arm is deferred to that owner, so this gap is advanced, not settled.",
        "The catalog was not edited (ledgers are frozen for this wave). Proposed catalog text for the coordinator: 'Alpaca cash_dividends.currency is optional; an absent/empty value means USD, not-applicable or unknown per the REST contract. Treat absent currency on a US-listed (foreign=false) cash dividend as USD for reconciliation, record the row as currency_assumed_usd, and keep it distinct from provider-stated USD.'",
        "The retained capture predates this docs fetch by 3 days; the provider may now emit currency on some rows (the SSE example does)."],
     "raw": ["1-ca-currency-probe.json", "1-alpaca-corporateactions-docs.excerpt.json", "REDACTIONS.json"]},
 12: {"slug": "ca-currency-shared-capture", "outcome": "advanced", "evidence_class": "source_review",
      "checked_at": "2026-09-23T04:24:19Z",
      "commands": ["Same evidence as gap 1 (receipt 1-ca-currency-field.json); no separate command."],
      "results": ["Same result as gap 1: currency is an optional REST property whose empty value can mean USD, N/A or unknown; the retained capture has no currency key; alpaca-py 0.44.0 does not model it."],
      "detection": "See gap 1 (key-scan positive control).",
      "limits": ["Fresh credentialed capture deferred to sota-workflow-resolution; catalog USD-assumption text drafted in the layer README, not written to the frozen catalog ledger. Cash-unit reconciliation stays incomplete until one of those lands."],
      "raw": ["1-ca-currency-probe.json"]},
 4: {"slug": "alpaca-py-latest-seams", "outcome": "settled", "evidence_class": "local_integration",
     "checked_at": "2026-09-23T04:35:41Z",
     "commands": [
        f"uv venv --python 3.13 {CACHE}/alpaca-latest && uv pip install alpaca-py   # via ecosystem-bounded-run; resolved 0.44.0",
        "curl -sS https://pypi.org/pypi/alpaca-py/json   # info.version 0.44.0, uploaded 2026-08-11",
        f"uv venv --python 3.13 {CACHE}/alpaca-master && uv pip install 'alpaca-py @ git+https://github.com/alpacahq/alpaca-py@232179c19091fd0f70daf0972a90bf8def329ec0'   # upstream master HEAD",
        f"bash {BP}/run_alpaca_seams.sh {CACHE}/alpaca-latest/bin/python",
        f"bash {BP}/run_alpaca_seams.sh {CACHE}/alpaca-master/bin/python",
        f"bash {BP}/retry_mutation.sh {CACHE}/alpaca-master/bin/python"],
     "results": [
        "Latest PyPI release is 0.44.0 (= the pinned version); upstream master HEAD 232179c = 0.44.0.post12.dev0; diff -rq of installed alpaca/ trees: only __init__.py differs; rest.py sha256 887753b0... identical",
        "seam probe (both prefixes): StockHistoricalDataClient and CorporateActionsClient _session_is_requests_Session=true, has__retry=true, default__retry=3",
        "0.44.0 prefix, unchanged tests/test_alpaca_historical.py: Ran 23 tests ... OK (0 skips); pin-lifted copy: Ran 23 tests ... OK",
        "master prefix, unchanged suite: FAILED (errors=3) - the three native-seam tests raise ValueError('alpaca_sdk_version_mismatch') (version pin guard working as designed); pin-lifted temp copy: Ran 23 tests ... OK",
        "negative control (master, `client._retry = 0` deleted in temp copy): AssertionError: 4 != 3 : native retry or redirect added an HTTP attempt -> mutant_exit=1"],
     "detection": "The 429/302 single-attempt assertion fails when the _retry seam no longer disables native retries (shown by the mutant run); seam attributes are checked by isinstance/hasattr.",
     "limits": [
        "No released version newer than the pin exists as of 2026-09-23, so the 'upgrade' arm could only exercise unreleased master HEAD (12 commits past 0.44.0, code-identical in alpaca/ apart from __init__.py). A future release can still break the private seams; the version pin plus these tests is the guard.",
        "Synthetic HTTP adapters only; no provider request."],
     "raw": ["4-alpaca-latest-tests.txt", "4-alpaca-master-tests.txt", "4-alpaca-master-retry-mutant.txt", "4-sdk-0440-vs-master-diff.txt", "4-pypi-alpaca-py.json", "4-alpaca-py-ls-remote.txt", "REDACTIONS.json", "install-alpaca-install.log", "install-alpaca-master-install.log"]},
 5: {"slug": "parameterized-comparator", "outcome": "advanced", "evidence_class": "local_integration",
     "checked_at": "2026-09-23T04:42:15Z",
     "commands": [f"bash {BP}/run_compare.sh", f"$HOME/.local/share/codex-ecosystem/tools/sdk-env-baseline-20260922/bin/python3 {BP}/diff_by_year.py {BP} lean-daily:... alpaca-parquet:... IBM,SPY,AAPL 2016-01-04 2021-03-31"],
     "results": [
        "original compare.py and compare_multi.py (lean-probe vs alpaca-run, AAPL, 2020-08-03..2020-09-04, --expect-sessions 25): per-symbol result identical: {\"identical\": true, \"keys_only_original\": [], \"keys_only_multi\": []} (bars 25/25 equal, max diff 0.00; actions reconciliation_incomplete, numeric_values_equal 2, unknown_currency 1)",
        "AAPL lean-probe vs alpaca-parquet (broad-market store): bars equal 25/25, max 0.00",
        "second symbols, lean-daily vs alpaca-parquet, same 25 sessions: IBM compared 25, different 1, max 0.0200; SPY compared 25, different 24, max 0.5106",
        "2016-01-04..2021-03-31: AAPL 1320 compared / 43 different / max 0.3400; IBM 1320 / 211 / 2.2100; SPY 1320 / 1214 / 7.1300; missing 0, extra 0 for all",
        "normalized-csv arm (provider-neutral export): clean IBM copy -> equal 25/25; one close +0.01 -> different 1, max 0.0100; --expect-sessions 24 -> ValueError unsupported_reference_session_count (exit 1)",
        "Fix round 1 (after Codex review raw/review-codex-round1.txt): unavailable reference -> {\"status\": \"unavailable\", \"reason\": \"reference_request_failed\"} (was reported equal); symbol absent from reference -> no_reference_sessions; alpaca-run actions filtered to requested symbols and in-range ex_date ([{\"symbol\": \"AAPL\", \"ex_date\": \"2020-08-07\"}] kept of 3 synthetic rows). All round-1 outputs unchanged apart from code hashes and one traceback line number; AAPL identical=true again."],
     "detection": "Negative control: a single +0.01 close perturbation in the normalized-csv arm flips status to differences (different=1); the session-count guard rejects a wrong expectation.",
     "limits": [
        "The parameterized comparator is a successor module under blueprints/gap-wave2-20260923/ (reusing compare.py's numeric validation); blueprints/us-equities/authenticated-data/compare.py itself was not edited because its hash is pinned in earlier receipts and it is outside this unit's owned paths. Promotion into the authenticated-data blueprint is left to the coordinator, so the gap text 'compare.py is hard-coded' still literally holds.",
        "No Databento or Massive data exists on this host and acquiring it needs paid/credentialed access; a Databento/Massive arm needs only a normalized CSV export (symbol,session_date,close) but that arm was exercised with a LEAN-derived CSV, not a real Databento/Massive export.",
        "Second-symbol disagreements (notably SPY on ~91% of sessions) are unexplained here: LEAN's bundled daily close and Alpaca's SIP daily close likely use different close definitions for ETFs; the comparator reports, it does not diagnose. The parquet arm converts stored doubles with repr() (shortest round-trip text).",
        "Private Alpaca data was read in memory only; only aggregate counts are published."],
     "raw": ["5-compare-multi-run.txt", "5-diff-by-year.json", "5-compare-multi-run.fix1.txt"]},
 6: {"slug": "us-venue-calendars-extended-hours", "outcome": "advanced", "evidence_class": "native_proven",
     "checked_at": "2026-09-23T13:29:13Z",
     "commands": [
        "curl -sSL -A 'Mozilla/5.0 (X11; Linux x86_64) research-check' https://www.nyse.com/markets/hours-calendars   # 200, redirected to /trade/hours-calendars, 109133 bytes",
        f"$HOME/.local/share/codex-ecosystem/tools/pandas-market-calendars-5.4.0/bin/python3 {BP}/calendar_check.py {CACHE}/docs/nyse-hours.html > {EV}/raw/6-calendar-check.json   # attempt 3; attempts 1-2 raised DateOutOfBounds (start, then end) and were fixed by padding the construction bounds",
        "# fix round 2 (after the Opus review):",
        "curl -sSL -A 'Mozilla/5.0 (X11; Linux x86_64) research-check' https://www.nasdaqtrader.com/Trader.aspx?id=Calendar   # 200, 54661 bytes",
        "curl -sSL -A '<same UA>' https://www.cboe.com/about/hours/   # 200, 382879 bytes (https://www.cboe.com/about/hours/us-equities/ returned 404)",
        "curl -sSL -A '<same UA>' https://www.nasdaq.com/stock-market-trading-hours-for-nasdaq   # 200, redirected to /market-activity/stock-market-holiday-schedule; same 2026 table as nasdaqtrader, not used as a separate source",
        f"python3 {BP}/publish_raw.py {EV}/raw 6-nasdaqtrader-holiday-calendar.html 6-cboe-hours-holidays.html   # UUID redaction plus 2 home-directory-shaped URL paths (nasdaqtrader links of the form slash-home-slash-index.jsp) redacted; hashes in REDACTIONS.json; the check output is byte-identical on the redacted copies",
        f"$HOME/.local/share/codex-ecosystem/tools/pandas-market-calendars-5.4.0/bin/python3 {BP}/venue_pages_check.py {EV}/raw/6-nasdaqtrader-holiday-calendar.html {EV}/raw/6-cboe-hours-holidays.html {EV}/raw/6-nyse-hours-calendars.html > {EV}/raw/6-venue-pages-check.fix2.json   # run on the cache originals, then re-run on the published copies: byte-identical (cmp)",
        "# fix round 3 (re-dispatched unit; preregistration-fix-round3.json 13:01:09Z, addendum 13:03:27Z, both committed before the parse):",
        "curl -sS 'https://web.archive.org/cdx/search/cdx?url=nyse.com/markets/hours-calendars&from=...&to=...&filter=statuscode:200'   # snapshot discovery for 2016, 2017, 2018, 2021, 2022, 2023, 2024, 2025 windows (one 2022 query hit 'Internet Archive: Temporarily Offline' and was retried)",
        "curl -sS 'https://web.archive.org/cdx/search/cdx?url=ir.theice.com/press/news-details/{2018,2024,2025}/&matchType=prefix&filter=original:.*(Bush|Carter|Mourning|close).*'   # found both ICE press releases",
        "curl -sS -o SNAP.html 'https://web.archive.org/web/<TS>id_/<URL>'   # NYSE hours-calendars snapshots 20160108005018, 20170301172132, 20181204174714, 20181215174802, 20210111130129, 20220706011712, 20230102062613, 20240111002222, 20250109223733, 20250115012652; ICE releases 20250108195503 (Bush) and 20241230155348 + 20241230201900 (Carter); the 20181204, 20230102 and 2025 NYSE snapshots have no holiday table (JS-rendered) and the Carter 20241230201900 copy is a stub without body text, so none of those is used",
        f"python3 {BP}/publish_raw.py {EV}/raw 14-wayback-nyse-20160108005018.html 14-wayback-nyse-20170301172132.html 14-wayback-nyse-20181215174802.html 14-wayback-nyse-20210111130129.html 14-wayback-nyse-20220706011712.html 14-wayback-nyse-20240111002222.html   # UUID redaction; original hashes in REDACTIONS.json (the two ICE pages were first published the same way, then replaced by the next step)",
        f"python3 {BP}/ice_text_publish.py {CACHE}/round3 {EV}/raw   # review-fix step: guarded gitleaks flagged the ICE HTML (generic-api-key: the ir.theice.com site's embedded public Q4 API key, 4 findings); the two press releases are published as tag-stripped text only, original HTML sha256 in REDACTIONS.json, full HTML kept in the cache; rerun after scripts/validate.py flagged Business Wire's third-party '/home/<id>' URL path, which is now redacted as in publish_raw.py (2 redactions, Bush text only). The press-page sha256 values inside 14-archive-calendar-check.fix3.json refer to the pre-redaction text; 14-archive-calendar-check.eolfix3.json carries the published ones",
        f"$HOME/.local/share/codex-ecosystem/tools/pandas-market-calendars-5.4.0/bin/python3 {BP}/archive_calendar_check.py --press {EV}/raw/14-wayback-ice-*.txt --nyse {EV}/raw/14-wayback-nyse-*.html > {EV}/raw/14-archive-calendar-check.fix3.json   # final run 4 (after the review fixes: documented extractor scope narrowed to the first date per verb, holiday self-test now injects a table row and re-parses); run 3 was the pre-review version; run 1 did not parse the 2018 table (bare <thead> header), run 2 paired a title 'Close' with a date ~1,600 chars later (verb-to-date distance now capped at 200); the final run on the cache originals and on the published copies is identical except file names and hashes (cmp)",
        f"$HOME/.local/share/codex-ecosystem/tools/pandas-market-calendars-5.4.0/bin/python3 {BP}/selftest_mutation.py {EV}/raw/14-wayback-nyse-20181215174802.html > {EV}/raw/14-selftest-mutation.fix3.txt   # review fix: the injected-cell self-test must fail when the cell parser is disabled",
        "# round-3 EOL integrity fix (eol_fix preregistration 13:25:21Z, committed in 1240cb9): git stores these raw HTML files with LF (.gitattributes '* text=auto eol=lf') but the worktree copies were CRLF, so recorded hashes did not match a fresh checkout",
        f"python3 {BP}/eol_normalize.py {EV}/raw 6-nasdaqtrader-holiday-calendar.html 7-quantconnect-terms.html 14-wayback-nyse-20160108005018.html 14-wayback-nyse-20170301172132.html 14-wayback-nyse-20181215174802.html   # worktree sha256 now equals the git blob sha256 for all five",
        f"$HOME/.local/share/codex-ecosystem/tools/pandas-market-calendars-5.4.0/bin/python3 {BP}/venue_pages_check.py {EV}/raw/6-nasdaqtrader-holiday-calendar.html {EV}/raw/6-cboe-hours-holidays.html {EV}/raw/6-nyse-hours-calendars.html > {EV}/raw/6-venue-pages-check.eolfix3.json   # identical to 6-venue-pages-check.fix2.json",
        f"$HOME/.local/share/codex-ecosystem/tools/pandas-market-calendars-5.4.0/bin/python3 {BP}/archive_calendar_check.py --press {EV}/raw/14-wayback-ice-*.txt --nyse {EV}/raw/14-wayback-nyse-*.html > {EV}/raw/14-archive-calendar-check.eolfix3.json   # identical to 14-archive-calendar-check.fix3.json except the three normalized files' sha256 fields; stderr empty"],
     "results": [
        "exchange_calendars 4.13.2 vs pandas_market_calendars 5.4.0, 2016-01-01..2027-12-31: XNYS~NYSE, XNAS~NASDAQ, ARCX~NYSE, XASE~NYSE, XNYS~BATS: 3016 sessions each, only_xcals [], only_pmc [], 24 early closes each, 0 early-close disagreements. ALIASING (disclosed in fix round 2): every one of these venue names resolves to the same NYSE rule set in both libraries (raw 6-calendar-check.fix1.json: xcals_calendar_objects ARCX/XASE/XNAS/XNYS = XNYSExchangeCalendar; pmc_calendar_objects NASDAQ/BATS/NYSE = NYSEExchangeCalendar; xcals alias table XNAS/ARCX/XASE/BATS/NASDAQ -> XNYS). The five pairs are therefore one comparison (xcals XNYS vs pmc NYSE) repeated, not per-venue evidence.",
        "pmc IEX calendar disagrees: 3041 sessions, 25 extra dates incl. every New Year's Day and Labor Day and 2018-12-05/2025-01-09; 12 early closes missing -> pmc 5.4.0 IEX calendar is not usable as a US holiday source",
        "pmc NYSE and NASDAQ extended schedule (start='pre', end='post'): 2992 sessions 04:00|09:30|16:00|20:00 ET, 24 early-close sessions 04:00|09:30|13:00|17:00 ET; exchange_calendars has no pre/post attributes (pre_opens/post_closes false)",
        "NYSE published page (years 2026, 2027, 2028): 29 holidays and 5 early closes (2026-11-27, 2026-12-24, 2027-11-26, 2028-07-03, 2028-11-24) - vs xcals XNYS and vs pmc NYSE: holidays_only_page [], holidays_only_library [], early_only_page [], early_only_library []",
        "NYSE page Arca hours: 'Early Trading Session: 4:00 a.m. to 9:30 a.m. ET', 'Late Trading Session: 4:00 p.m. to 8:00 p.m. ET'; early-close days: Arca/American/National/Texas late sessions close at 5:00 p.m. -> matches pmc pre/post 04:00/20:00 and 17:00 on early closes",
        "Fix round 1 (after Codex review): per-session open AND close time comparison added: 0 disagreements for XNYS~NYSE, XNAS~NASDAQ, ARCX~NYSE, XASE~NYSE, XNYS~BATS (the aliased NYSE rule set); IEX 12. NYSE page now compared against every library close != 16:00 and requires 13:00 on page dates: all lists empty for both libraries. Self-test: an injected 10:00 open and 14:00 close are both reported (self_test_detected=true). Ad-hoc closures, controls and extended-hours sections unchanged.",
        "Fix round 2, per-venue published corroboration (independent of the libraries): Nasdaq's 'U.S. Equity and Options Markets Holiday Schedule 2026' (nasdaqtrader.com) lists 10 closed days and 2 early closes at 1:00 p.m. (2026-11-27, 2026-12-24); vs xcals XNAS, pmc NASDAQ, xcals XNYS and pmc NYSE: holidays_only_page [], holidays_only_library [], early_only_page [], early_only_library [], early_time_mismatch [] (agree=true for all four).",
        "Fix round 2: Cboe's '2026 Equities Holiday Schedule' (cboe.com/about/hours, covering Cboe BZX/BYX/EDGX/EDGA equities) lists 10 closed days and 2 early closes (Thanksgiving Early Close 2026-11-27, Christmas Early Close 2026-12-24; the page publishes no early-close time); vs pmc BATS and xcals XNYS: all difference lists empty (agree=true).",
        "Fix round 2: NYSE page scope statement 'All NYSE markets observe U.S. holidays as listed below for 2026, 2027, and 2028.' - the 2026-2028 NYSE-page corroboration therefore applies directly to NYSE Arca and NYSE American (XASE), not only indirectly.",
        "Fix round 2, extended hours per venue (published): NYSE Arca Equities early session 4:00 a.m.-9:30 a.m.; NYSE American, NYSE National and NYSE Texas 7:00 a.m.-9:30 a.m.; Cboe BZX/EDGX early session 4:00 a.m.; Cboe BYX/EDGA 7:00 a.m.; all late/post sessions end 8:00 p.m. pmc's single pre/post schedule (04:00/20:00) matches Arca and BZX/EDGX only; it is not per-venue for American, National, Texas, BYX or EDGA.",
        "Fix round 2 self-test: an injected extra holiday (2026-03-10) and a shifted early close (2026-11-27 at 14:00) are both reported (detected=true); parser_detection_ok=true (>= 9 holidays parsed from each page).",
        "Fix round 3, archived NYSE published tables (Internet Archive snapshots of nyse.com/markets/hours-calendars, each stating 'All NYSE markets observe U.S. holidays as listed below for ...'): the latest snapshot listing each year matches xcals XNYS and pmc NYSE exactly (holidays both directions and 1:00 p.m. early closes) for every year 2016-2026: 2016 (20160108), 2017 (20170301), 2018-2020 (20181215), 2021 (20210111), 2022-2023 (20220706), 2024-2026 (20240111). With the fix-round-2 live page (2026-2028), NYSE-markets published corroboration now spans 2016-2028.",
        "Fix round 3: the only per-snapshot mismatches are in the 20210111 snapshot's forward years (2022-06-20 and 2023-06-19 library-only): that page predates NYSE's adoption of Juneteenth, and the later 20220706 snapshot lists both dates, matching the libraries. The tables omit the ad-hoc closures (reported separately as library_adhoc_closures 2018-12-05 and 2025-01-09).",
        "Fix round 3 self-tests (after the review fix): a holiday row injected into each snapshot's HTML table and re-parsed is reported page-only for every snapshot (6/6); with the cell parser disabled (mutant parse_cell returning None) the same self-test reports false, so it detects parser failure (raw 14-selftest-mutation.fix3.txt); every compared snapshot-year met the >= 9 parsed-holiday floor except 2022 in the 20210111 snapshot (8: no New Year observance and no Juneteenth yet), which is reported, not hidden."],
     "detection": "Set differences in both directions per venue pair; the IEX pair shows the method reports disagreements (25 dates). Positive controls 2018-12-04/06 and 2025-01-08/10 are sessions in every calendar. Fix round 2: page-vs-library set differences in both directions plus early-close time equality; injected holiday and early-close time are reported (self-test), and each page must yield >= 9 parsed holidays.",
     "limits": [
        "Security-specific trading halts (LULD pauses, regulatory halts) are not modelled by either library and were not checked; this clause of the gap remains open.",
        "Library venue names are aliases of one NYSE rule set in both libraries, so the library comparison alone is not per-venue evidence. Per-venue published corroboration: NYSE markets (incl. Arca and American) 2016-2028 (archived tables in fix round 3 plus the live page); Nasdaq and Cboe 2026 only. Nasdaq and Cboe schedules for 2016-2025 and 2027 rest on the aliased NYSE rule set; this remains open.",
        "IEX, NYSE National, NYSE Texas and Cboe BYX/EDGA/EDGX have no separate library calendar here (pmc IEX is wrong, see results); their holidays are corroborated only through the NYSE and Cboe pages for their published years.",
        "pmc pre/post boundaries match NYSE Arca's published extended hours; NYSE Tape A itself publishes no 04:00 early session, so pre/post are consolidated/venue-dependent, not per-venue truth.",
        "NYSE corroboration for 2016-2025 (fix round 3) comes from Internet Archive copies of NYSE's page, not from NYSE directly; each snapshot's timestamp and sha256 are retained. 2027 rests on the live page only.",
        "Attempts 1 and 2 of calendar_check.py failed with exchange_calendars DateOutOfBounds (stderr retained); the fix only padded construction bounds."],
     "raw": ["6-calendar-check.json", "6-nyse-hours-calendars.html", "REDACTIONS.json", "6-calendar-check.attempt1.stderr", "6-calendar-check.attempt2.stderr", "6-calendar-check.stderr", "6-calendar-check.fix1.json", "6-calendar-check.fix1.stderr",
             "6-venue-pages-check.fix2.json", "6-venue-pages-check.fix2.stderr", "6-nasdaqtrader-holiday-calendar.html", "6-cboe-hours-holidays.html",
             "14-archive-calendar-check.fix3.json", "14-archive-calendar-check.fix3.stderr", "14-wayback-ice-bush-20250108195503.txt", "14-wayback-ice-carter-20241230155348.txt", "14-selftest-mutation.fix3.txt", "review-codex-round3.txt", "14-archive-calendar-check.eolfix3.json", "6-venue-pages-check.eolfix3.json", "14-wayback-nyse-20160108005018.html", "14-wayback-nyse-20170301172132.html", "14-wayback-nyse-20181215174802.html", "14-wayback-nyse-20210111130129.html", "14-wayback-nyse-20220706011712.html", "14-wayback-nyse-20240111002222.html"]},
 14: {"slug": "adhoc-closures-nyse-corroboration", "outcome": "advanced", "evidence_class": "native_proven",
      "checked_at": "2026-09-23T13:29:13Z",
      "commands": ["Same runs as gap 6: calendar_check.py over the retained NYSE page and, in fix round 2, venue_pages_check.py over the Nasdaq, Cboe and NYSE pages (see 6-us-venue-calendars-extended-hours.json).",
        "# fix round 3 (re-dispatched unit; preregistration-fix-round3.json 13:01:09Z, addendum 13:03:27Z, both committed before the parse):",
        "curl -sS 'https://web.archive.org/cdx/search/cdx?url=nyse.com/markets/hours-calendars&from=...&to=...&filter=statuscode:200'   # snapshot discovery for 2016, 2017, 2018, 2021, 2022, 2023, 2024, 2025 windows (one 2022 query hit 'Internet Archive: Temporarily Offline' and was retried)",
        "curl -sS 'https://web.archive.org/cdx/search/cdx?url=ir.theice.com/press/news-details/{2018,2024,2025}/&matchType=prefix&filter=original:.*(Bush|Carter|Mourning|close).*'   # found both ICE press releases",
        "curl -sS -o SNAP.html 'https://web.archive.org/web/<TS>id_/<URL>'   # NYSE hours-calendars snapshots 20160108005018, 20170301172132, 20181204174714, 20181215174802, 20210111130129, 20220706011712, 20230102062613, 20240111002222, 20250109223733, 20250115012652; ICE releases 20250108195503 (Bush) and 20241230155348 + 20241230201900 (Carter); the 20181204, 20230102 and 2025 NYSE snapshots have no holiday table (JS-rendered) and the Carter 20241230201900 copy is a stub without body text, so none of those is used",
        f"python3 {BP}/publish_raw.py {EV}/raw 14-wayback-nyse-20160108005018.html 14-wayback-nyse-20170301172132.html 14-wayback-nyse-20181215174802.html 14-wayback-nyse-20210111130129.html 14-wayback-nyse-20220706011712.html 14-wayback-nyse-20240111002222.html   # UUID redaction; original hashes in REDACTIONS.json (the two ICE pages were first published the same way, then replaced by the next step)",
        f"python3 {BP}/ice_text_publish.py {CACHE}/round3 {EV}/raw   # review-fix step: guarded gitleaks flagged the ICE HTML (generic-api-key: the ir.theice.com site's embedded public Q4 API key, 4 findings); the two press releases are published as tag-stripped text only, original HTML sha256 in REDACTIONS.json, full HTML kept in the cache; rerun after scripts/validate.py flagged Business Wire's third-party '/home/<id>' URL path, which is now redacted as in publish_raw.py (2 redactions, Bush text only). The press-page sha256 values inside 14-archive-calendar-check.fix3.json refer to the pre-redaction text; 14-archive-calendar-check.eolfix3.json carries the published ones",
        f"$HOME/.local/share/codex-ecosystem/tools/pandas-market-calendars-5.4.0/bin/python3 {BP}/archive_calendar_check.py --press {EV}/raw/14-wayback-ice-*.txt --nyse {EV}/raw/14-wayback-nyse-*.html > {EV}/raw/14-archive-calendar-check.fix3.json   # final run 4 (after the review fixes: documented extractor scope narrowed to the first date per verb, holiday self-test now injects a table row and re-parses); run 3 was the pre-review version; run 1 did not parse the 2018 table (bare <thead> header), run 2 paired a title 'Close' with a date ~1,600 chars later (verb-to-date distance now capped at 200); the final run on the cache originals and on the published copies is identical except file names and hashes (cmp)",
        f"$HOME/.local/share/codex-ecosystem/tools/pandas-market-calendars-5.4.0/bin/python3 {BP}/selftest_mutation.py {EV}/raw/14-wayback-nyse-20181215174802.html > {EV}/raw/14-selftest-mutation.fix3.txt   # review fix: the injected-cell self-test must fail when the cell parser is disabled",
        "# round-3 EOL integrity fix (eol_fix preregistration 13:25:21Z, committed in 1240cb9): git stores these raw HTML files with LF (.gitattributes '* text=auto eol=lf') but the worktree copies were CRLF, so recorded hashes did not match a fresh checkout",
        f"python3 {BP}/eol_normalize.py {EV}/raw 6-nasdaqtrader-holiday-calendar.html 7-quantconnect-terms.html 14-wayback-nyse-20160108005018.html 14-wayback-nyse-20170301172132.html 14-wayback-nyse-20181215174802.html   # worktree sha256 now equals the git blob sha256 for all five",
        f"$HOME/.local/share/codex-ecosystem/tools/pandas-market-calendars-5.4.0/bin/python3 {BP}/venue_pages_check.py {EV}/raw/6-nasdaqtrader-holiday-calendar.html {EV}/raw/6-cboe-hours-holidays.html {EV}/raw/6-nyse-hours-calendars.html > {EV}/raw/6-venue-pages-check.eolfix3.json   # identical to 6-venue-pages-check.fix2.json",
        f"$HOME/.local/share/codex-ecosystem/tools/pandas-market-calendars-5.4.0/bin/python3 {BP}/archive_calendar_check.py --press {EV}/raw/14-wayback-ice-*.txt --nyse {EV}/raw/14-wayback-nyse-*.html > {EV}/raw/14-archive-calendar-check.eolfix3.json   # identical to 14-archive-calendar-check.fix3.json except the three normalized files' sha256 fields; stderr empty"],
      "results": [
        "Ad-hoc closures 2018-12-05 (G. H. W. Bush) and 2025-01-09 (J. Carter): closed in xcals XNYS, XNAS, ARCX, XASE and pmc NYSE, NASDAQ, BATS; pmc IEX wrongly lists both as sessions. Because XNAS/ARCX/XASE (xcals) and NASDAQ/BATS (pmc) are aliases of the NYSE rule set (fix round 2 disclosure), this is two independent implementations (xcals XNYS, pmc NYSE), not seven venues.",
        "positive controls 2018-12-04, 2018-12-06, 2025-01-08, 2025-01-10 present in every calendar: true",
        "NYSE published 2026-2028 holidays and 1:00 p.m. early closes: zero differences vs both libraries",
        "pmc NYSE pre/post: 04:00-09:30 and 16:00-20:00 ET; 17:00 post close on early-close days (NYSE page: late sessions close at 5:00 p.m.)",
        "Fix round 1: same rerun as gap 6; ad-hoc closure and NYSE-page results unchanged under the stricter open/close and any-early-close comparisons (self-test detects injected disagreements).",
        "Fix round 2: Nasdaq (nasdaqtrader.com) and Cboe publish 2026 holiday schedules that agree exactly with the libraries (see gap 6); NYSE states the listed 2026-2028 holidays apply to all NYSE markets. None of the three pages lists past years, so they give no non-code corroboration of the 2018-12-05 and 2025-01-09 closures.",
        "Fix round 2 pre/post per venue: published early sessions start 4:00 a.m. (NYSE Arca, Cboe BZX/EDGX) or 7:00 a.m. (NYSE American, National, Texas, Cboe BYX/EDGA); pmc's single 04:00/20:00 schedule matches only the 4:00 a.m. venues.",
        "Fix round 3, non-code corroboration of the ad-hoc closures (archived ICE press releases): 'The New York Stock Exchange, NYSE American, NYSE National, NYSE Arca, and the Chicago Stock Exchange ... will be closed on Wednesday, December 5, 2018 in observance of the National Day of Mourning for President George H. W. Bush' (ICE, Dec 01, 2018); '...it will close all NYSE Group equity and options markets on Thursday, January 9, 2025, in observance of the National Day of Mourning...' and the closing markets are 'the New York Stock Exchange, NYSE American Equities, NYSE American Options, NYSE Arca Equities, NYSE Arca Options, NYSE Chicago and NYSE National' (ICE, Dec 30, 2024). Extractor output: closure_dates 2018-12-05 and 2025-01-09 only; adhoc_corroborated both true.",
        "Fix round 3 detection: the extractor takes the first 'Month D, YYYY' date within 200 characters after each closure verb in the same sentence (review fix: documented scope narrowed; a list 'closed on A and B' would report A only, and each retained release names one closure date); injected closure sentence reported and injected 'open' sentence not reported; negative controls on the real pages hold (2018-12-03 moment-of-silence date next to 'close' in the Bush headline and 2024-12-29 date of death are not reported).",
        "Fix round 3, comprehensive holidays: archived NYSE tables match both libraries for every year 2016-2026 (see gap 6 receipt); with the live 2026-2028 page, published NYSE-markets corroboration spans 2016-2028."],
      "detection": "Closure dates tested for absence from each session list with adjacent-day positive controls; IEX shows a failing calendar is reported. Fix round 2: page-vs-library self-test reports an injected holiday and early-close time.",
      "limits": [
        "Security-specific halts remain uncovered (no halt feed checked).",
        "The ad-hoc closure notices are ICE (NYSE Group) releases retrieved from the Internet Archive; they cover the NYSE Group markets they name. No Nasdaq or Cboe notice for those dates was retrieved, so those venues' closures on 2018-12-05 and 2025-01-09 rest on the aliased library rule set.",
        "Per-venue published corroboration covers NYSE markets 2016-2028 (archived tables plus live page) and Nasdaq and Cboe 2026 only; earlier Nasdaq and Cboe schedules rest on the aliased NYSE rule set."],
      "raw": ["6-calendar-check.json", "6-nyse-hours-calendars.html", "6-calendar-check.fix1.json", "6-venue-pages-check.fix2.json", "6-nasdaqtrader-holiday-calendar.html", "6-cboe-hours-holidays.html", "14-archive-calendar-check.fix3.json", "14-archive-calendar-check.fix3.stderr", "14-wayback-ice-bush-20250108195503.txt", "14-wayback-ice-carter-20241230155348.txt", "14-selftest-mutation.fix3.txt", "review-codex-round3.txt", "14-archive-calendar-check.eolfix3.json", "6-venue-pages-check.eolfix3.json", "14-wayback-nyse-20160108005018.html", "14-wayback-nyse-20170301172132.html", "14-wayback-nyse-20181215174802.html", "14-wayback-nyse-20210111130129.html", "14-wayback-nyse-20220706011712.html", "14-wayback-nyse-20240111002222.html"]},
 7: {"slug": "data-licensing-clauses", "outcome": "advanced", "evidence_class": "source_review",
     "checked_at": "2026-09-23T13:25:49Z",
     "commands": [
        "curl -sSL https://alpaca.markets/disclosures   # 200",
        "curl -sSL https://files.alpaca.markets/disclosures/library/{AcctAppMarginAndCustAgmt,TermsAndConditions,NYSE+Market+Data+Display+Services+Agreement,NASDAQ+OMX+Global+Subscriber+Agreement}.pdf   # all 200",
        "curl -sSL -A '<project-URL UA>' https://www.sec.gov/about/privacy-information   # 403 'Request Rate Threshold Exceeded' (live sec.gov blocked for this host)",
        "curl http://web.archive.org/web/20260919152816id_/https://www.sec.gov/about/privacy-information ; .../20260821173111id_/https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data",
        f"{CACHE}/pdf/bin/python (pypdf 6.19.0) PDF->text; python3 {BP}/license_clauses.py {CACHE}/docs > {EV}/raw/7-license-clauses.json   # missing_anchors []",
        "# fix round 2 (after the Opus review): LEAN/QuantConnect bundled data used by compare_multi.py (lean-daily, lean-probe sources)",
        "curl -sSL -A 'Mozilla/5.0 (X11; Linux x86_64) research-check' https://www.quantconnect.com/terms/   # 200, 79948 bytes; https://www.quantconnect.com/terms/data/ redirected to /login (not readable without an account)",
        f"python3 {BP}/publish_raw.py {EV}/raw 7-quantconnect-terms.html; cp $HOME/.local/share/codex-ecosystem/tools/lean-985ef30-remediation/{{LICENSE,Data/equity/readme.md}} {EV}/raw/",
        f"python3 {BP}/lean_rights.py $HOME/.local/share/codex-ecosystem/tools/lean-985ef30-remediation {EV}/raw/7-quantconnect-terms.html > {EV}/raw/7-lean-rights.fix2.json   # exit 0, missing_anchors []",
        "# round-3 EOL integrity fix (eol_fix preregistration 13:25:21Z, committed in 1240cb9): git stores these raw HTML files with LF (.gitattributes '* text=auto eol=lf') but the worktree copies were CRLF, so recorded hashes did not match a fresh checkout",
        f"python3 {BP}/eol_normalize.py {EV}/raw 6-nasdaqtrader-holiday-calendar.html 7-quantconnect-terms.html 14-wayback-nyse-20160108005018.html 14-wayback-nyse-20170301172132.html 14-wayback-nyse-20181215174802.html   # worktree sha256 now equals the git blob sha256 for all five",
        f"python3 {BP}/lean_rights.py $HOME/.local/share/codex-ecosystem/tools/lean-985ef30-remediation {EV}/raw/7-quantconnect-terms.html > {EV}/raw/7-lean-rights.eolfix3.json   # exit 0; identical to 7-lean-rights.fix2.json except the QuantConnect page sha256; stderr empty"],
     "results": [
        "Alpaca Customer Agreement V26.2026.07 s.30 'Use of Market Data': 'AlpacaDB, Inc. provides market data to non-professional Alpaca customers ... I agree not to reproduce, distribute, sell or commercially exploit the market data in any manner without written consent from Alpaca.'; it incorporates the NASDAQ OMX Global Subscriber Agreement and the Agreement for Market Data Display Services 'if I am provided access to such data'",
        "Alpaca Terms and Conditions: 'Content is provided exclusively for personal and noncommercial access and use. No part of the Service or Content may be copied, reproduced, republished, uploaded, posted, publicly displayed, encoded, translated, transmitted or distributed in any way (including \"mirroring\") to any other computer, server, web site or other medium for publication or distribution or for any commercial enterprise, without Alpaca's express prior written consent.'",
        "NYSE Market Data Display Services Agreement s.5: 'Subscriber shall not furnish Market Data to any other person or entity.'; Nonprofessional Subscriber = natural person receiving market data 'solely for his/her personal, non-business use'",
        "NASDAQ Global Subscriber Agreement: non-professional 'Information is licensed only for personal use'; 'Subscriber shall take reasonable security precautions to prevent unauthorized Persons from gaining access to the Information.'",
        "SEC (archived 2026-09-19): 'Information presented on sec.gov is considered public information and may be copied or further distributed by users of the web site without the SEC's permission. Please consider appropriate citation to the SEC as the source.'; fair access: no more than 10 requests per second; EDGAR (archived 2026-08-21): 'Anyone can access and download this information for free'; declare a User-Agent",
        "Storage: no Alpaca/NYSE/Nasdaq document found here contains a clause permitting or forbidding private local retention of historical market data; the operative limits are personal/non-commercial use, no furnishing/redistribution, and security against unauthorized access. Scan of store/retain/archive/cache/mirroring terms retained per document.",
        "Fix round 2, LEAN bundled data: the files this layer used (Data/equity/usa/daily/{aapl,ibm,spy}.zip at LEAN 985ef30, 2026-09-18) are tracked in the LEAN git repository, whose only license is Apache-2.0 ('Copyright 2014 QuantConnect Corporation'): '2. Grant of Copyright License ... to reproduce, prepare Derivative Works of, publicly display, publicly perform, sublicense, and distribute the Work'; '4. Redistribution. You may reproduce and distribute copies of the Work ... provided that You meet the following conditions: (a) You must give any other recipients ... a copy of this License'. No data-specific license, notice or terms file exists under Data/ and no Data readme mentions a license or redistribution (both lists empty).",
        "Fix round 2: Data/equity/readme.md: 'QuantConnect hosts US Equity Data (market 'USA') provided by AlgoSeek ... (trade and quote data from post-2007) and QuantQuote (trade data from pre-2007)' - the upstream vendors' own terms for the bundled sample were not found.",
        "Fix round 2: QuantConnect site Terms (quantconnect.com/terms) govern the Site, not the GitHub repository: '2.1 License. ... limited license to use and access the Site solely for your own personal use'; '2.2 Certain Restrictions ... you shall not license, sell, rent, lease, transfer, assign, distribute, host, or otherwise commercially exploit the Site ... or any content displayed on the Site'; '(xv) modify, distribute, redistribute or translate underlying works based on the Site'. The QuantConnect data-agreement URL requires login."],
     "detection": "Each clause is located by an exact anchor phrase; license_clauses.py and lean_rights.py exit 1 and list missing anchors if any is absent (missing_anchors = [] for both); lean_rights.py's self-test confirms a made-up anchor is reported missing.",
     "limits": [
        "Outcome advanced, not settled: (1) the account-specific Alpaca market-data plan and subscriber status (Basic/Algo Trader Plus, professional vs non-professional) that govern the data actually acquired were not read; that needs account access, owner sota-workflow-resolution. (2) For the LEAN sample data, only the repository license (Apache-2.0, no data carve-out) and QuantConnect's site terms were found; the AlgoSeek/QuantQuote vendor terms and QuantConnect's login-gated data agreement were not read.",
        "Not legal advice or a legal interpretation; clauses are quoted, not construed. Whether QuantConnect's Apache-2.0 grant validly covers vendor-sourced sample data is not assessed.",
        "Live sec.gov returned 403 'Request Rate Threshold Exceeded' for this host, so SEC statements come from Internet Archive snapshots dated 2026-09-19 and 2026-08-21.",
        "Consequence for the repository: raw Alpaca payloads must stay private (already the practice); SEC-derived data may be republished with citation."],
     "raw": ["7-license-clauses.json", "7-AcctAppMarginAndCustAgmt.pypdf.txt", "7-TermsAndConditions.pypdf.txt", "7-NYSE_Market_Data_Display_Services_Agreement.pypdf.txt", "7-NASDAQ_OMX_Global_Subscriber_Agreement.pypdf.txt", "7-sec-privacy-information-wb20260919.html", "7-sec-accessing-edgar-data-wb20260821.html", "7-sec-live-403-response.html", "REDACTIONS.json",
             "7-lean-rights.fix2.json", "7-lean-rights.fix2.stderr", "7-lean-LICENSE.txt", "7-lean-Data-equity-readme.md", "7-quantconnect-terms.html", "7-lean-rights.eolfix3.json"]},
 8: {"slug": "feast-pit-join", "outcome": "advanced", "evidence_class": "local_integration",
     "checked_at": "2026-09-23T04:42:57Z",
     "commands": [
        f"uv venv --python 3.12 {CACHE}/feast && uv pip install feast   # via ecosystem-bounded-run; feast 0.66.0, pandas 2.3.3, pyarrow 25.0.1; uv cache 562 MB downloaded in total for this unit",
        f"HOME=$(mktemp -d) {CACHE}/feast/bin/python {BP}/feast_pit_fixture.py > {EV}/raw/8-feast-pit-fixture.json   # final run exit 0; attempt 1 exit 1 retained"],
     "results": [
        "Feast 0.66.0 local provider, file offline store, get_historical_features: AAA@2020-02-01 -> 1.0 (oracle 1.0); AAA@2020-05-01 -> 1.15 (restatement with later created_timestamp wins; oracle 1.15); AAA@2020-06-30 -> 1.15 (value published 2020-07-10 NOT joined; future_value_leaked=false)",
        "CCC (no feature rows) returned with null; BBB (only a row older than the 365-day TTL) is DROPPED from the result: entity_rows_in 5, rows_returned 4",
        "attempt 1 (without CCC) exited 1 because its TTL check expected a null row for BBB and got none (rows_returned 3 of 4)",
        "Alpaca news fetch: not run (credentialed provider contact belongs to sota-workflow-resolution)",
        "Fix round 1 (after Codex review): join cardinality check added (Counter of returned (symbol, ts) keys must not exceed the requested keys): join_cardinality_ok=true; self-tests reject an appended duplicate row and an unrequested ZZZ row (both true). Values unchanged."],
     "detection": "Every returned row is compared with an independent filter-and-sort oracle; the 2020-07-10 value (1.20) is explicitly searched for as the leakage signal; dropped entity rows are enumerated by comparing input and output keys.",
     "limits": [
        "Alpaca news native evidence deferred (owner: sota-workflow-resolution; needs paper credentials).",
        "Macro-vintage, stream-ingestion and server-store scope terms were not exercised (no feature server, no stream source, no ALFRED/vintage data); they remain without native evidence.",
        "Synthetic 5-row fixture, local file offline store only; Feast's silent drop of stale-only entity rows is a PIT-research hazard (row loss instead of explicit null) and should be handled by a left-join guard if Feast is adopted.",
        "Feast pulled a ~430 MB venv and was installed only under the cache prefix; no Feast server or port was started."],
     "raw": ["8-feast-pit-fixture.json", "8-feast-pit-fixture.stderr", "8-feast-pit-fixture.attempt1.json", "8-feast-pit-fixture.attempt1.stderr", "install-feast-install.log", "8-feast-pit-fixture.fix1.json", "8-feast-pit-fixture.fix1.stderr"]},
 17: {"slug": "sec-api-python-disposition", "outcome": "advanced", "evidence_class": "source_review",
      "checked_at": "2026-09-23T04:31:58Z",
      "commands": [f"bash {BP}/repo_review.sh SEC-API-io/sec-api-python {EV}/raw/17-gh", "curl -sS https://pypi.org/pypi/sec-api/json"],
      "results": [
        "repo: MIT license, 320 stars, 41 forks, 1 open issue, created 2021-06-12, pushed 2026-04-13, not archived, homepage https://sec-api.io; single contributor janlukasschroeder (45 commits)",
        "latest release v1.0.36 published 2026-04-13; PyPI sec-api 1.0.36 uploaded 2026-04-13",
        "README: 'Get your free API key on sec-api.io ... replace YOUR_API_KEY'; client for the sec-api.io hosted API (20M+ filings, 'survivorship-bias free' entities, datasets download); package is a thin HTTP client (sec_api/index.py) with no local EDGAR parsing",
        "Disposition: not adopted for the SEC acquisition requirement. It requires a third-party sec-api.io account/API key (hosted, metered service beyond a free tier) and returns derived data whose own terms would govern reuse, whereas the requirement is met by free primary EDGAR access (EdgarTools / direct EDGAR, public information per SEC). Keep as a catalogued paid alternative (keep-but-compare) for bulk historical filings if direct EDGAR access stays rate-blocked; overturn: a measured comparison where direct EDGAR cannot supply a required filing set within fair-access limits and sec-api terms permit the intended storage."],
      "detection": "gh api exit codes retained per endpoint; 404s would be recorded as errors (none for this repository).",
      "limits": ["sec-api.io pricing/terms pages not fetched; the paid-service characterization rests on the README's API-key requirement and the hosted-API design.", "Outcome advanced, not settled (fix round 2, same standard as gap 1): the next_check's 'record a catalog disposition' arm is not executed. The disposition is drafted in this receipt only; this unit may not edit catalogs/landscape/*.json, so the alternative stays unindexed until the coordinator writes the disposition to the ledger."],
      "raw": ["17-gh-repo.json", "17-gh-release-latest.json", "17-gh-releases.json", "17-gh-tags.json", "17-gh-license.json", "17-gh-commits.json", "17-gh-readme.json", "17-gh-tree.json", "17-gh-contributors.json", "17-pypi-sec-api.json", "REDACTIONS.json"]},
 18: {"slug": "rossod4-quantlab-disposition", "outcome": "advanced", "evidence_class": "source_review",
      "checked_at": "2026-09-23T04:32:12Z",
      "commands": [f"bash {BP}/repo_review.sh Rossod4/quantlab {EV}/raw/18-gh", "gh api repos/Rossod4/quantlab/contents/{plans/M01-data-providers.md,pyproject.toml,src/quantlab/data/pit.py}"],
      "results": [
        "repo: 'Bias-free systematic equity research platform (in progress): point-in-time data layer, SEC EDGAR fundamentals, survivorship measurement'; license null and /license 404 (no license file -> all rights reserved); 0 stars, 0 forks; created 2026-08-07, pushed 2026-09-12; single contributor Rossod4 (40 commits); no releases (releases/latest 404), no tags; /readme 404",
        "data-reference scope (tree + files): src/quantlab/data/{pit.py, corporate_actions.py, adjustment.py, survivorship.py, cache.py, quality.py}, providers {yfinance_prices, edgar_fundamentals, sp500_constituents, norgate_prices (stub)}; pyproject depends on exchange-calendars and yfinance; PITDataContext hard-binds strategy data access to one asof date and filters future-dated rows",
        "Disposition: not adopted. No license (code cannot be reused), no releases, one contributor, 5 weeks old; its data path relies on yfinance (unofficial Yahoo scraping with unclear redistribution rights) and Wikipedia-style S&P 500 membership, which do not add a qualified data source beyond the catalog's Alpaca/EDGAR/LEAN path. The PITDataContext invariant (single asof-bound accessor that filters future rows) is recorded as a design idea only; overturn: an OSI license plus a native run showing a capability the adopted stack lacks."],
      "detection": "gh api exit codes and 404 bodies retained (18-gh-*.err) so missing license/README/release are evidence, not silence.",
      "limits": ["No install or test run of quantlab (unlicensed; nothing to adopt).", "Outcome advanced, not settled (fix round 2, same standard as gap 1): the next_check's 'record a catalog disposition' arm is not executed. The disposition is drafted in this receipt only; this unit may not edit catalogs/landscape/*.json, so the alternative stays unindexed until the coordinator writes the disposition to the ledger."],
      "raw": ["18-gh-repo.json", "18-gh-release-latest.json", "18-gh-release-latest.err", "18-gh-releases.json", "18-gh-tags.json", "18-gh-license.json", "18-gh-license.err", "18-gh-commits.json", "18-gh-readme.json", "18-gh-readme.err", "18-gh-tree.json", "18-gh-contributors.json", "18-gh-contents-plans_M01-data-providers.md.json", "18-gh-contents-pyproject.toml.json", "18-gh-contents-src_quantlab_data_pit.py.json"]},
}


REVIEW = {
 5: "2 findings (unavailable reference reported equal; actions not filtered by symbol/range) - both fixed in round 1 and re-run",
 6: "2 findings (opening times not compared; NYSE-page check limited to 13:00 closes) - both fixed in round 1 and re-run",
 14: "same 2 calendar findings as gap 6 - fixed in round 1 and re-run",
 8: "1 finding (join cardinality: duplicate/unrequested rows accepted) - fixed in round 1 and re-run",
}


REVIEW2 = {
 6: "major: venue pairs are aliases of one NYSE rule set, per-venue corroboration missing - aliasing disclosed; Nasdaq and Cboe published 2026 schedules and the NYSE all-markets statement added (fix round 2); outcome stays advanced",
 14: "major (shared with gap 6): aliasing disclosed and per-venue pages added; ad-hoc closures still lack a non-code source",
 7: "major: settled although LEAN data rights and account-plan terms were uncovered - LEAN repository license and QuantConnect terms added; outcome changed settled -> advanced (account-plan terms and vendor terms remain)",
 17: "minor: catalog-write standard inconsistent with gap 1 - outcome changed settled -> advanced (ledger write not executed by this unit)",
 18: "minor: catalog-write standard inconsistent with gap 1 - outcome changed settled -> advanced (ledger write not executed by this unit)",
 1: "minor (standard applied to gaps 17/18): no change; the catalog USD-assumption arm stays open",
}


def main():
    units = json.loads(Path(sys.argv[1]).read_text())
    unit = next(u for u in units if u["layer_id"] == "market-data-reference")
    gaps = {g["index"]: g for g in unit["gaps"]}
    prereg = json.loads((ROOT / EV / "preregistration.json").read_text())
    fix = json.loads((ROOT / EV / "preregistration-fix-round1.json").read_text())
    fix2 = json.loads((ROOT / EV / "preregistration-fix-round2.json").read_text())
    fix3 = json.loads((ROOT / EV / "preregistration-fix-round3.json").read_text())
    if set(gaps) != set(RECEIPTS):
        raise SystemExit(f"gap set mismatch: {sorted(gaps)} vs {sorted(RECEIPTS)}")
    for idx, r in RECEIPTS.items():
        p = prereg["gaps"][str(idx)]
        if p is None or prereg["written_at"] >= r["checked_at"]:
            raise SystemExit(f"preregistration not before results for gap {idx}")
        if str(idx) in fix2["gaps"] and fix2["written_at"] >= r["checked_at"]:
            raise SystemExit(f"fix-round-2 preregistration not before results for gap {idx}")
        if idx in (6, 7, 14) and fix3["eol_fix"]["written_at"] >= r["checked_at"]:
            raise SystemExit(f"eol-fix preregistration not before results for gap {idx}")
        if str(idx) in fix3["gaps"] and max(fix3["addendum"]["written_at"], fix3["review_fix"]["written_at"]) >= r["checked_at"]:
            raise SystemExit(f"fix-round-3 preregistration not before results for gap {idx}")
        receipt = {
            "id": f"gap-wave2-20260923/us-equities__market-data-reference/{idx}-{r['slug']}",
            "gap_index": idx, "layer_id": "market-data-reference", "catalog": "us-equities",
            "gap_text": gaps[idx]["text"],
            "gap_text_sha256": hashlib.sha256(gaps[idx]["text"].encode()).hexdigest(),
            "next_check": gaps[idx]["next_check"],
            "preregistration": {"written_at": prereg["written_at"], "expectation": p["expectation"], "criteria": p["criteria"],
                                "source": str(EV / "preregistration.json"), "committed_in": "c6846f1"},
            "fix_round_preregistration": ({"written_at": fix["written_at"], "label": fix["label"], **fix["gaps"][str(idx)],
                                           "source": str(EV / "preregistration-fix-round1.json"), "committed_in": "0481e46"}
                                          if str(idx) in fix["gaps"] else None),
            "fix_round2_preregistration": ({"written_at": fix2["written_at"], "label": fix2["label"], **fix2["gaps"][str(idx)],
                                            "source": str(EV / "preregistration-fix-round2.json"), "committed_in": "5f248b6"}
                                           if str(idx) in fix2["gaps"] else None),
            "fix_round3_preregistration": ({"written_at": fix3["written_at"], "label": fix3["label"], **fix3["gaps"][str(idx)],
                                            "addendum": fix3["addendum"], "review_fix": fix3["review_fix"],
                                            "source": str(EV / "preregistration-fix-round3.json"), "committed_in": ["97cf2a8", "4074556 (addendum)", "107cfdf (review_fix)"]}
                                           if str(idx) in fix3["gaps"] else None),
            "eol_fix_preregistration": ({**fix3["eol_fix"], "source": str(EV / "preregistration-fix-round3.json"), "committed_in": "1240cb9"}
                                        if idx in (6, 7, 14) else None),
            "independent_review_round3": ({"reviewer": "codex exec --sandbox read-only --ephemeral over the uncommitted round-3 diff, stdin from /dev/null, 79,605 tokens",
                                           "output": str(EV / "raw" / "review-codex-round3.txt"),
                                           "findings_for_this_gap": "2 minor (extractor documented as reporting every date, but takes the first date per verb; holiday self-test bypassed the parser); no blocker or major; both fixed under the review_fix preregistration and rerun"}
                                          if str(idx) in fix3["gaps"] else None),
            "independent_review_round2": {"reviewer": "independent Opus review of fe8b66e (findings relayed by the coordinator)",
                                          "findings_for_this_gap": REVIEW2.get(idx, "none")},
            "independent_review": {"reviewer": "codex exec --sandbox read-only --ephemeral (codex-cli 0.155.1); invocation 1 stalled reading stdin and was stopped without output, invocation 2 (stdin from /dev/null) completed, 62,448 tokens",
                                   "output": str(EV / "raw" / "review-codex-round1.txt"),
                                   "findings_for_this_gap": REVIEW.get(idx, "none (helpers for this gap were not in the review scope)")},
            "commands": r["commands"], "results": r["results"], "detection_method": r["detection"],
            "outcome": r["outcome"], "evidence_class": r["evidence_class"], "limits": r["limits"],
            "raw_artifacts": raw(*r["raw"]), "checked_at": r["checked_at"],
            "checked_at_source": "UTC mtime of the latest raw output the receipt cites (sed path-redaction can postdate the run by seconds)",
            "host_paths": "host paths are written as $HOME; private Alpaca payloads stay outside the repository"}
        (ROOT / EV / f"{idx}-{r['slug']}.json").write_text(json.dumps(receipt, indent=1, ensure_ascii=False) + "\n")
    # results.json is generated from the receipt files on disk, never from RECEIPTS directly.
    results = {}
    for f in sorted((ROOT / EV).glob("[0-9]*-*.json"), key=lambda p: int(p.name.split("-")[0])):
        d = json.loads(f.read_text())
        results[str(d["gap_index"])] = {"outcome": d["outcome"], "receipt": str(EV / f.name)}
    (ROOT / EV / "results.json").write_text(json.dumps(results, indent=1) + "\n")
    print(json.dumps({k: v["outcome"] for k, v in results.items()}))


if __name__ == "__main__":
    main()
