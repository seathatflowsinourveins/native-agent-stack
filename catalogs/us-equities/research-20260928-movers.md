# Mover research refresh, 2026-09-28

This record answers three questions for the north star, all asked while the paper lane restarted:
- **R1:** where to get historical daily extreme movers;
- **R2:** which factors have published evidence for pre-positioning or continuation;
- **R3:** what has changed since the 2026-09-26 trading convergence for the engine, full-market monitor,
  strategy-framework and research-RAG layers.

**How it was produced.** Three read-only Claude `stack-researcher` subagents (latest Opus, effort max) ran
between 16:03Z and 16:40Z. Their baseline was PR #358 at `c1f40f0e` (the 13-layer convergence) and PR #360
at `af38dced` (Mover v3, pre-freeze). They opened no Mover v3 sealed file, outcome data or pinned study data.

Evidence tags:
- **D:** a cited document says so.
- **O:** observed on 2026-09-28.
- **A:** from an abstract only.
- **U:** unverified.

The coordinator re-checked two claims against source, and they are marked "(re-checked)". Everything else
is worker output to verify before a decision rests on it.

## Paper-lane context on this date

The PC series `pc-20260928` is frozen and has not started.
- **What it would run:** adaptive-paper mover mode at main `3058b237`, mechanics-only rule
  `10:00|G20|V250000|any`, exit X2, rung 4 under the canonical leverage block.
- **Why it hasn't started:** Alpaca's paper trading API returns HTTP 401 for the stored paper key.
  - The scan's `GET /v2/calendar` at 12:02:53 ET got 401.
  - `tools/credentials/alpaca_rate_limit_probe.py` sent `GET /v2/account` at 16:03:25Z and got 401.
- **This predates today.** PR #360's body already says "paper keys currently return 401" (re-checked).
- **Next input:** the user stores a new paper pair with
  `tools/credentials/open_credential_terminal.sh alpaca-paper --probe`. No order has been sent.

## R1: historical daily extreme movers

**What the repo has.**
- The v1/v2 mover study used private Alpaca SIP daily bars for 2021-01-04 to 2026-09-18.
  - Candidates: 236,538 symbol-days whose adjusted high reached at least 1.20 × the prior low, excluding OTC.
  - Its holdout, 2026-01-02 to 09-18, was never read (`mover-early-entry/protocol.json:12-24,121-123`).
  - Result: 0 of 768 v1 rule-exits pass development, and no v2 family passes (`mover-early-entry/README.md:16-40`).
- The study's candidate set holds 498 of the price audit's 594 verified +20% events (83.8%). That is under
  its own 95% bar (`protocol.json:126`).
  - In the 3–10× tier it holds 28 of 43.
  - The cause is collection by today's symbol (`broad-universe/collect_daily.py:6-9`): a reused ticker
    resolves to its current holder. The extreme-gainer audit instead priced each event `asof` its date.
- Reusable assets:
  - a SIP universe of 24,664 symbols from 2016;
  - five +200% label definitions (`catalyst-experiment/README.md:56-62`);
  - the ≥10× tier's split-artifact finding;
  - EDGAR Form 25 counts for 2016–2019.
- Still-open gates (`gates-20260922.json:120-185`): `pre-2020-delisting`, `dated-security-identity`,
  `pit-news-filings`, and `databento-arm-b`, which waits on a paid entitlement.

**Recommendation, free first.**
1. **Alpaca SIP, re-collected with a historical `asof`**, raw and split-adjusted.
   - The account's measured 10,000 calls/min data limit is the Algo Trader Plus tier
     (`data-lake/README.md:3-5`, re-checked).
   - Tiingo's free `supported_tickers.csv` gives an extra seed of delisted tickers; how many Alpaca serves is U.
   - Overturn: re-collecting the 96 missed events recovers under 95% coverage. Then use a paid source.
2. **SEC EDGAR for catalysts:** the submissions API, nightly `submissions.zip` and full-text search since
   2001 (D); edgartools 5.59.1 is current (O).

**Paid options (the user decides; none is authorized by this record).**
- **Massive Starter, 29 USD a month.** Grouped daily bars cover every stock for one date per call. Reference
  tickers carry `delisted_utc`, CIK and FIGI back to 2003. The splits endpoint flags `reverse_split` (D).
  - Overturn: under 2% more verified +50% events after split filtering.
- **Sharadar Prices, 39 USD a month.** 21,000 active and delisted stocks since 1997, with listing and
  delisting actions (D). Choose it over Massive for pre-2016 depth.
- **Databento Standard, 199 USD a month.** Official EQUS.SUMMARY end-of-day data and a security master
  since 2005 (D). It suits intraday detail on mover days more than discovery.
- **EODHD (19.99 USD) and Tiingo Power (30 USD).** Both are possible; their delisted coverage in bulk is U.
- **yfinance** serves only as a negative control.
- No maintained open-source extreme-mover history exists (O).

**Next steps.**
1. Fix the 401.
2. Freeze a `plan.json` before fetching: ratios 1.5, 2 and 3, the five labels, sources and tolerances.
3. Re-fetch the 96 missed events with `feed=sip&adjustment=raw&asof=<event date>`, keeping outputs outside git.
4. After the close, check that the recipe reproduces 2026-09-28's KOD and LFCR as a positive control.

**Mover v3 guard.** Until v3's freeze commit:
- publish only coverage and vendor-agreement totals;
- keep event lists and return columns outside git, committed only as sha256;
- the dataset builder does not review v3.

Computing outcomes over 2026-01-02 to 09-18 ends that window's untouched status, and must be recorded when
it happens.

## R2: factor evidence for extreme movers

**Answer.** Published evidence does not support pre-positioning ahead of catalyst jumps like KOD's +149%.
- Event studies condition on the outcome, so they show no entry edge.
- Ex-ante lottery traits predict *low* returns: MAX in Bali, Cakici & Whitelaw 2011, skewness and jackpot
  probability. Hou, Xue & Zhang 2020 finds MAX fails on NYSE value-weighted breakpoints and survives only
  as a microcap effect.
- Option flow before deals is largely non-public information.
- The supported pattern is post-detection, news-conditioned continuation over several days.
  - Jiang, Li & Wang 2021 claims profitability after costs (A; its universe is U).
  - Jiang & Zhu 2017, Chan 2003 and Da, Liu & Schaumburg 2014 point the same way.
- **Leverage cannot fix a negative expectancy.** The v1 leveraged portfolio lost at every rung.

**What the repo already tested, all negative after costs.**
- v1: 768 rule-exits, median mean net −2.9%.
- v2: first-cross entries, opening-range and VWAP setups, and four prior-close scores. Its volume-breakout
  set held 11.7% of next-day ≥+100% movers against a 0.004% base rate and still lost money.
- Never tested: float, short interest, borrow, news semantics, options, after-hours and halt history.
- The v3 draft tests H1 (MAX21 terciles) and H3 (overnight versus intraday legs). It defers H2 catalysts,
  H4 halts and H5 days-to-cover.

**Next preregistered candidates, strongest evidence first.**
1. **Continuation after news-aligned jumps, held t+1 to t+5.** It is blocked by the H2 data gates:
   look-ahead news tags and no as-known CIK map.
   - Overturn: validation mean net ≤ 0 on the winsorised, top-5-sessions-removed or per-session means,
     or news-minus-no-news ≤ 0.
2. **Predicted jump probability** (Kapadia & Zekhnini 2019). It is the only positive ex-ante jump premium;
   costs and inputs are U.
   - Overturn: the high-minus-low validation mean net ≤ 0.
3. **Buying before scheduled catalysts versus matched non-event days.** This is the direct test of KOD-style
   entry, and it has the weakest support. Entries may use only dates known in advance: FDA advisory
   committee meetings have Federal Register notice at least 15 days ahead (21 CFR 14.20(a)). An as-known
   earnings schedule is U.
   - Overturn: event-window mean net ≤ 0, or event-minus-matched ≤ 0.

**Cost and decay context.**
- 65% of 452 anomalies fail replication, 96% under trading frictions (Hou, Xue & Zhang 2020).
- Post-publication returns are 58% lower (McLean & Pontiff 2016).
- Strategies above 50% monthly turnover rarely survive (Novy-Marx & Velikov 2016).

## R3: layer deltas since #358

| Layer | Selection | Change since 2026-09-26 | Decision | Overturn / next |
| --- | --- | --- | --- | --- |
| Trade engine | NautilusTrader 2.0.0rc5, custom Alpaca adapter, alpaca-py 0.44.0; LEAN comparator | No tag after rc5. develop's RELEASES.md opens an unreleased 2.0.0rc6 with 68 breaking changes and live-reconciliation fixes (O). NT PR #5041 now targets ibapi 4.2.0 and is still open; runtime-target pins 4.1.0. No NT IB market scanner; the Rust `ibapi` crate has `scanner_subscription`. No upstream Alpaca adapter (RFC #3374 open). alpaca-py and LEAN unchanged. | Unchanged | Re-run the frozen IBKR paper receipt plus restart reconciliation when v2.0.0rc6 is tagged |
| Full-market monitor | `blueprints/us-equities/incentive-monitor/`: SIP snapshots of about 13,191 symbols in about 27 calls; screeners as side lists | No upstream doc change (O). Doc facts not in the repo record: `movers` returns at most 50 per side and "resets at market open", so it cannot surface pre-market gappers; one stream connection per endpoint (406); Basic is IEX-only at 200/min, while SIP needs Algo Trader Plus (D). IBKR scans return at most 50 rows with at most 10 active. | Unchanged | Test detection latency of the 20 s snapshot sweep against engine-owned `*` bars in the same session |
| Strategy frameworks | None | Checked: QuantConnect research 18444 (Stocks-in-Play ORB, 2016 only, no tests); two single-instrument Zarattini replications with tests (Sharpe claims U). None targets +100/200% movers. | None qualifies | Replicate QC 18444 as a bounded arm under a frozen protocol on the LEAN oracle. 2021 is not a fresh holdout. |
| Research RAG | None; the web-research layer is used | paper-qa v2026.08.12 (last commit 08-12). On LitQA2, PaperQA2 scores 85.2% precision and 66.0% accuracy (D). In AstaBench, the ReAct/gpt-5, Falcon and Crow intervals overlap (D). PaperQA3 is hosted only (self-hosting U). ai2-scholar-qa 0.8.13; OpenScholar stale. Transfer to finance is U. | Open | A frozen QA set from #358's 25 verified papers, comparing paper-qa, ai2-scholar-qa and the Tavily lane in an upstream harness (asta-bench/agent-eval) |

## Decisions recorded

- **No layer selection changes.** Each row above names the comparison that would overturn it.
- **Today's paper series is mechanics-only.** It is labelled that way because 0 of 768 rule-exits passed
  development. Leverage in it is the user's instruction, not an evidence-backed edge.
- **Research priorities for the next preregistration** (Mover v3's owner decides what enters v3):
  1. the free `asof` re-collection;
  2. the news-aligned continuation test;
  3. a scheduled-catalyst test using only dates known in advance.

## Sources

**Repo and PRs.**
- `blueprints/us-equities/{mover-early-entry, broad-universe, extreme-gainer-audit, delisting-coverage,
  catalyst-experiment, data-lake, incentive-monitor}/README.md`
- `catalogs/us-equities/gates-20260922.json`, `catalogs/us-equities/runtime-target.json`
- PR #358 at `c1f40f0e` and PR #360 at `af38dced`

**Market data vendors.**
- Alpaca:
  - https://docs.alpaca.markets/us/docs/about-market-data-api
  - https://docs.alpaca.markets/us/reference/stockbars
  - https://docs.alpaca.markets/us/reference/movers-1
  - https://docs.alpaca.markets/us/docs/streaming-market-data
- Massive:
  - https://massive.com/docs/rest/stocks/aggregates/daily-market-summary
  - https://massive.com/pricing
- Sharadar: https://sharadar.com/prices
- Databento: https://databento.com/equities
- EODHD: https://eodhd.com/pricing
- SEC:
  - https://www.sec.gov/search-filings/edgar-application-programming-interfaces
  - 21 CFR 14.20(a)
  - 17 CFR 242.201

**Papers.**
- Bali, Cakici & Whitelaw 2011, doi:10.1016/j.jfineco.2010.08.014
- Hou, Xue & Zhang 2020, doi:10.1093/rfs/hhy131
- Kapadia & Zekhnini 2019, doi:10.1016/j.jfineco.2018.08.014
- Jiang, Li & Wang 2021, doi:10.1016/j.jfineco.2021.04.003
- Jiang & Zhu 2017, doi:10.1016/j.jfineco.2016.06.006
- Chan 2003, doi:10.1016/S0304-405X(03)00146-6
- Da, Liu & Schaumburg 2014, doi:10.1287/mnsc.2013.1766
- Gao, Han, Li & Zhou 2018, doi:10.1016/j.jfineco.2018.05.009
- McLean & Pontiff 2016, doi:10.1111/jofi.12365
- Novy-Marx & Velikov 2016, doi:10.1093/rfs/hhv063
- Chen & Zimmermann 2022, doi:10.1561/104.00000112 (code: OpenSourceAP/CrossSection@8db89244)
- Singh et al. 2022, doi:10.1371/journal.pone.0272851

**Engines and RAG.**
- `nautechsystems/nautilus_trader@b916d058:RELEASES.md`
- https://github.com/nautechsystems/nautilus_trader/pull/5041
- https://github.com/alpacahq/alpaca-py/releases
- https://www.quantconnect.com/research/18444/opening-range-breakout-for-stocks-in-play/
- https://github.com/Future-House/paper-qa/releases/tag/v2026.08.12
- https://arxiv.org/abs/2409.13740
- https://arxiv.org/abs/2510.21652
