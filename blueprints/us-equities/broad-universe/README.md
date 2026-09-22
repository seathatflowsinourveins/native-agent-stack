# Broad US-equities universe: measured coverage, frozen mover protocol, dated scan

This blueprint widens research beyond the 24-symbol adaptive-paper fixture. It is
research tooling only: no order, account, position or execution endpoint appears in
any module, and nothing here changes a paper risk limit. SPY is used as the session
calendar and a context reference, never as the strategy universe.

| File | Role |
| --- | --- |
| `protocol.json` | `broad-universe-mover-v1-20260921`, frozen before any historical return was computed |
| `collect_daily.py` | paginated SIP daily bars (raw + fully adjusted), every page retained with hash and ledger |
| `corporate_actions.py` | market-wide corporate actions, calendar-year windows, retained pages |
| `coverage.py` | materialises `daily.parquet`, removes duplicated ticker series, builds the measured manifest |
| `evaluate.py` | chronological event study of the five predeclared signals against the all-eligible control |
| `scan.py` | dated full-universe scan with session determination, staleness labels and pinned names |
| `receipt.json` | sanitised measured results (counts, dates, symbols, statistics; no prices or provider text) |

Source pins: alpaca-py 0.44.0 runtime (requests 2.34.2, DuckDB 1.5.5) against the current
[historical bars](https://docs.alpaca.markets/us/reference/stockbars),
[corporate actions](https://docs.alpaca.markets/reference/corporateactions-1),
[snapshots](https://docs.alpaca.markets/us/reference/stocksnapshots-1),
[movers](https://docs.alpaca.markets/us/reference/movers-1) and
[news](https://docs.alpaca.markets/us/reference/news-3) contracts. All requests are HTTPS GET.

## What the access actually is (measured 2026-09-21)

- **Real-time SIP is entitled** on the research paper profile: `feed=sip` latest quotes answered
  HTTP 200 with timestamps seconds old; `delayed_sip` trailed by about 15 minutes and `iex`
  stopped at the regular close. The adaptive fixture's `feed: iex` is its frozen setting, not the limit.
- SIP bars begin 2016-01-04 (1Day) and 2016-01-01 (1Min). Nothing earlier is served.
- `feed=otc` answered 403 for the probed OTC symbol; OTC is outside this dataset.
- News reaches back to 2015-01; corporate actions are available market-wide but are thin before 2020.
- Provider movers/most-actives screens are bounded top-N lists dominated by sub-$5 names and warrants.
  They are shown beside the scan, never as market coverage.

## Coverage manifest (measured, not sampled)

See `receipt.json` → `coverage` for the exact numbers. Headlines:

- 24,664 symbols requested: 15,418 from the asset master (active + inactive, excluding 17,456 OTC
  rows and 418 CUSIP-style placeholders) plus a 9,246-symbol **supplement**.
- 2,554 pages per adjustment, 24,310,292 bars per adjustment, 0 failed batches, 0 retries.
  Pagination proof: 496 symbol groups, 0 violations. All 5,108 retained pages re-hashed with 0 mismatches.
  CSV row totals equal ledger totals. An independent one-symbol-at-a-time re-fetch of 20 symbols × 2
  adjustments matched the bulk dataset for every symbol the bulk run had requested.
- 17,997 symbols have bars over 2,693 sessions (2016-01-04 → 2026-09-18); 24,195,741 symbol-sessions
  after identity dedup. META and AMD: 2,693 sessions each, no gaps.
- Eligible universe under the protocol (close ≥ $5, prior-20-session median dollar volume ≥ $20M,
  ≥ 60 prior bars): median 1,302 names per session in 2016 rising to 2,634 in 2026.

Two provider behaviours were found by independent observation and are handled in code:

1. **The asset list under-enumerates delisted names.** `TWTR` is served by the bars API and by
   `/v2/assets/TWTR` but is absent from `/v2/assets?status=inactive`. The supplement is seeded from
   every symbol referenced by retained corporate actions, minus renamed-away old tickers.
   2,676 supplement symbols have bars.
2. **A renamed-away ticker is answered with its successor's history.** `FB` (today a ProShares ETF)
   and `META` both carried Meta's 2016–2022 bars. `coverage.dedupe_identity` decides from an
   immutable snapshot, requires ≥ 20 identical sessions covering ≥ 98% of the dropped symbol's span,
   resolves rename chains as connected components, removes a predecessor's row only where a
   higher-ranked paired member has a bar (so a staggered chain keeps every session exactly once),
   and records the rule used per pair: 155 pairs (42 rename record, 59 price continuity, 48 active
   status, 6 lexicographic and flagged `identity_unresolved`), 114,551 rows removed of which 229 were
   non-identical residue; 2,071 rows kept because no surviving copy existed. 80 partial overlaps
   (27,877 identical sessions, 0.12% of rows) fail the 98% test and are left untouched and counted.

Open coverage gates (none is hidden by the numbers above):

- **Survivorship before 2020.** Symbols whose last bar falls in 2016/2017/2018 number 25/47/167,
  against 541–756 per year for 2021–2025. Corporate-action records are sparse before 2020
  (name changes: 57 in 2017–2019 versus 304–700 per year after), so names delisted in 2016–2019
  without a retained action cannot be discovered from entitled sources.
- No listing/delisting dates and no historical security type; 235 asset-master ticker collisions
  cannot be dated. Fund status uses the current asset name and is reported beside an unfiltered lane.
- Bars downloaded on 2026-09-21 do not prove what was published at each historical close.
- Minute bars and quotes are entitled from 2016 but are not collected market-wide here.

`feed=iex` daily history starts 2020-07-27 for the probed names, so SIP (2016-01-04) is the widest
entitled daily source; minute SIP bars answered from 2016-01-01 and for delisted `TWTR` to 2022-10-27.

## Frozen protocol and what it measured

`protocol.json` was committed (`24e4cd8`, mechanical clarification `311fa6b`) before any historical
return was computed; `evaluate.py` was written against synthetic fixtures only and ran on real bars
**once**, at `3da95cd`, after both review lanes cleared it. It deliberately does not reuse the frozen
catalyst protocol's $1–$50 band: there is no price cap, so META and AMD are in scope.

- Decision after the close of session *t* from bars ≤ *t*; eligibility on raw prices (close ≥ $5,
  prior-20-session median dollar volume ≥ $20M, 60 contiguous prior bars); returns on the fully
  adjusted series; entry at the *t+1* open; exits at the *t+1*, *t+5*, *t+20* closes; 5/10/20 bps per
  side by liquidity tier, stress ×3; delisted series exit at the last close (stress −50%).
- Five predeclared signals (S1 momentum breakout, S2 volume-shock continuation, S3 oversold
  reversal, S4 contraction breakout, S5 gap-and-hold), the all-eligible control C0, a 5% hash
  placebo C1, two instrument lanes and a descriptive sub-$5 lane. No parameter search.
- Development 2017–2021, validation 2022–2023, reserved 2024-01-01 → 2026-08-14. Realised movers
  are labels only: they measure precision, base rate, lift and recall, never the candidate set.

### Result: no signal is established

4,577,640 scored main-universe decisions, 45,406,248 events, 378 metric groups, 71 s. All 15
signal × horizon promotion checks return `not_established`. Primary lane, all events, date-clustered
mean net **excess over C0** in percent (Bonferroni interval), development | validation | reserved:

| Signal | H1 (open→close) | H5 | H20 |
| --- | --- | --- | --- |
| S1 momentum breakout | −0.16 (−0.35..+0.02) \| −0.02 \| −0.06 | +0.05 \| −0.36 \| −0.24 | −0.28 \| −1.12 \| −0.44 |
| S2 volume-shock continuation | **−0.33 (−0.61..−0.03)** \| −0.04 \| −0.20 | −0.39 \| −0.39 \| −0.37 | −0.55 \| −0.57 \| −1.06 |
| S3 oversold reversal | −0.19 \| +0.12 \| −0.01 | −1.07 \| +0.17 \| −0.80 | −1.02 \| +0.25 \| −0.67 |
| S4 contraction breakout | −0.04 \| −0.03 \| **−0.13 (−0.26..−0.01)** | −0.16 \| −0.12 \| −0.19 | +0.42 \| −0.39 \| +0.27 |
| S5 gap-and-hold | −0.41 \| −0.14 \| −0.24 | −0.59 \| −0.19 \| −0.82 | −0.71 \| +0.10 \| −1.39 |

No interval lies above zero in any segment; the only intervals that exclude zero are negative
(bold). The placebo C1 sits at zero as it should. 55–61% of H1 signal events lose money after costs
(`failed_share`), against 55–57% for the control. The control itself loses 0.21–0.25% per
open→close round trip: the cost of trading, not a signal.

**Do the flags find movers beforehand?** They find *volatility*, not direction. Reserved segment,
+10% next-day movers: base rate 0.72%; precision S2 4.6%, S5 4.0%, S3 2.6%, S1 2.3%, S4 0.7% —
and the same flags carry a 5–6× lift for −10% movers. Recall is 1–3%: **97–99% of next-day
+10% movers in the liquid universe carried no prior flag**, and 95–99% of flagged names did not move.
For ≥ +20% in one day (reserved base rate 0.11%) the best precision is 1.1%. Finding past winners in
the labels does not show a rule could have selected them.

META and AMD were eligible on every scored session (1,259 / 501 / 657 decisions by segment). Their
flag counts are descriptive only (AMD development: S1 24, S2 20, S4 25, S5 11).

Limits of this result: daily bars only (no opening-auction price, halts, LULD or quotes); event
study, not a portfolio simulation; the survivorship gap above biases 2017–2019 upward; identity is
provider-symbol based; bootstrap blocks are consecutive entry dates per selector and the Bonferroni
bound from 2,000 resamples is noisy. A negative result is kept as a result; any new variant needs a
new protocol version and can no longer treat 2024–2026 as untouched.

## Dated scan: session 2026-09-21 (run 23:48 UTC / 19:48 ET, after-hours)

`watchlist-20260921.json` is the sanitised output (symbols, ranks, rounded moves, buckets, flags,
timestamps; no prices, quotes or headline text). Session state came from the provider clock and
calendar: regular session 2026-09-21 closed, previous session 2026-09-18, next open 2026-09-22 09:30 ET.

- 13,171 active tradable non-OTC symbols scanned with SIP snapshots in 30 GETs; 2 missing,
  12,561 with a bar for today, 164 showing only the previous session and 444 older (`stale_bar`).
  After the close the daily bar may still be revised by late prints.
- 1,795 names eligible in the operating-company lane (2,651 without the fund-name filter); 607 had
  non-contiguous history and 4 stale history, reported as unknown rather than guessed.
- **META +11.3% and AMD +9.9% were large movers but not the top**: #14 and #19 of 1,795 by percent
  change, #2 and #4 by dollar volume. 18 eligible names moved ≥ 10%, led by GRAL, NUAI, FSLY, YSS,
  AXTI, FIVN; the largest decliners were CXW, NVO, RSI, MHK.
- 55 names carry a research flag (S4 42, S1 10, S5 8, S2 6, S3 3). META shows S1+S2 and AMD
  S1+S2+S5 — the same flags the evaluation above found to have no established edge. They are
  `research_flag_not_prediction`.
- The provider's movers screen for the same moment was headed by sub-$5 names and warrants
  (e.g. +230%, +186%); it is listed separately as a bounded top-N screen, not market coverage.
- 40 timestamped news items (created/updated/observed times, source, symbols, url host and hashes)
  for the pinned names and the top 20 movers; context only, never scored as expected return.

## Paper qualification

No candidate was advanced and no order was placed. Nothing met the promotion requirements; the
market was closed for the whole task; and the frozen adaptive-paper trial is a 300-second intraday
trial that ends flat, which a next-open-to-later-close study cannot fit without a separately reviewed
execution design. The account was observed ACTIVE with 0 positions and 0 open orders, no trader
process was running, and the existing weekday 09:35/13:35 ET heartbeat remains the only order writer.

## Reproduce

```sh
PY=<isolated runtime with alpaca-py 0.44.0, requests, duckdb, pandas, numpy>
$PY collect_daily.py --env-file "$PAPER_ENV_FILE" --assets active.json inactive.json \
    --out "$PRIVATE/dataset" --end 2026-09-18T23:59:59Z
$PY corporate_actions.py collect --env-file "$PAPER_ENV_FILE" --out "$PRIVATE/corporate-actions"
$PY collect_daily.py ... --supplement-symbols supplement-symbols.json      # same --out, series "s"
$PY coverage.py materialize --dataset "$PRIVATE/dataset" --corporate-actions "$PRIVATE/corporate-actions" --assets active.json inactive.json
$PY coverage.py build --dataset "$PRIVATE/dataset" --assets active.json inactive.json --probe probe.json --out manifest.json
$PY evaluate.py run --daily "$PRIVATE/dataset/daily.parquet" --assets active.json inactive.json \
    --protocol protocol.json --out results.json --events-out "$PRIVATE/events.parquet" \
    --commit "$(git rev-parse HEAD)" --ledger-sha256 "$LEDGER_SHA" --run-at "$(date -u +%FT%TZ)"
$PY scan.py run --env-file "$PAPER_ENV_FILE" --history "$PRIVATE/dataset/daily.parquet" --pinned META,AMD \
    --assets-out assets.json --out-private scan.json --out-public watchlist.json
python3 -m unittest tests.test_broad_universe_coverage tests.test_broad_universe_evaluate tests.test_broad_universe_scan
```

A changed request scope refuses to resume into an existing output directory. The evaluation peaked
at 13.1 GB resident memory with a 12 GB DuckDB limit.

## Review

Codex foreground lane (`/codex:review --scope branch`, four passes, status 0 each: 13, 5, 2 and 1
comments) and three native Opus reviewers (24 findings) reviewed the branch independently and
converged on the same defects. Every supported finding was fixed with a regression test that fails
on the pre-fix code; the last pass raised only a performance point. 158 local synthetic tests pass
in the research runtime and the default interpreter skips cleanly without DuckDB. Agreement between
reviewers is not the acceptance evidence: the page-hash and row-total proofs, the independent
re-fetch and the regression tests are.
