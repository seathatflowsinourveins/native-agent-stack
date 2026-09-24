# Mover study v3: research plan (2026-09-24)

**Status: draft plan. Nothing here is frozen, and no outcome has been computed.** The preregistration draft is
[`protocol-draft.json`](protocol-draft.json), status `draft_pending_independent_pre_outcome_review`. The engineering
hypothesis H6 has its own draft, [`h6-execution-parity-draft.json`](h6-execution-parity-draft.json). The catalog
decisions from the same sweep are in
[`catalogs/us-equities/mover-v3-sweep-20260924.json`](../../../catalogs/us-equities/mover-v3-sweep-20260924.json).

**Evidence class.** This plan rests on literature and metadata evidence, plus a few unpinned source reads, all from a
read-only SOTA sweep on 2026-09-24. It is not native execution. The sweep had five angles (literature, repositories,
data, exits and sizing, execution) and proposed 37 items. At least two independent verifiers checked each item:
**5 survive, 24 are contested and 8 were killed.** This plan uses only the surviving items, plus contested items whose
refutation the sweep's synthesis judged weak. Those are labelled *contested* wherever they are used. No market data
was fetched, no study code was run, and no paper order was placed. The sweep input (sha256 `e2120c05...64d1`) stays
private because its verifier notes contain host paths. This README and the supplement carry its content.

**Relation to PR #162.** PR #162 merged to main on 2026-09-24 as squash commit `aa6fc79`. It holds the mover
early-entry v1 and v2 studies (`blueprints/us-equities/mover-early-entry/**`). **v1: 0 of 768 rule-exits pass
development. v2: no pass in families E, F or P** (results sha256 `75a5004b...` after deviation D7). v3 does not modify
those files. It reuses their pipeline only by reference, pinned to main at `aa6fc79` with git-blob and sha256 hashes
for `rules.py`, `quotes.py`, `sessions_io.py` (`official_price` only), the cost table and `evaluate_v2.py` (for D7's
split and ex-dividend accounting only; `protocol-draft.json`). The pin includes D7's stamp-window guard in `quotes.py`.
That code is valid for 2021-2026 only: its early-close list starts in 2021 and its fee file has no SEC rate before
2020. v3 therefore owns an XNYS session calendar (`exchange_calendars` 4.13.2) and a fee file with sourced 2017-2020
rows, both pinned at the freeze, and never calls `rules.py`'s close-time or fee functions. The earlier pin `92062e8` survives only on the PR branch. v3 does not read #162's reserved holdout. The
2021 control segment of the catalyst experiment is permanently inspected and is not a fresh holdout.

## Why continuation is not supported

The v1 premise is that an extreme recent mover with high volume keeps rising early in its move, net of costs. The
evidence below points the other way. It is consistent with #162's result, not a sign of an engineering bug:

| Evidence | What it says | Sweep status |
|---|---|---|
| Bali, Cakici, Whitelaw (2011), "Maxing Out", *JFE* 99(2) ([PDF](https://pages.stern.nyu.edu/~rwhitela/papers/max%20jfe.pdf); [NBER w14804](https://www.nber.org/system/files/working_papers/w14804/w14804.pdf)) | Stocks with the largest recent daily return (MAX) earn *lower* subsequent risk-adjusted returns: lottery demand, then reversal | **survives** (both PDFs opened) |
| Hong, Li, Ni, Scheinkman, Yan, "Days to Cover and Stock Returns" ([NBER w21166](https://www.nber.org/system/files/working_papers/w21166/w21166.pdf)) | High days-to-cover predicts *lower* returns. The paper makes no squeeze claim | **survives** (opened) |
| Barber & Odean (2008), *RFS* 21(2) ([PDF](https://faculty.haas.berkeley.edu/odean/papers/Attention/All%20that%20Glitters.pdf)); Barber, Huang, Odean, Schwarz (2022), *JF* ([10.1111/jofi.13183](https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.13183)); Barber, Lin, Odean (2023), *JFQA* | Retail buying of extreme-return, high-volume names is well documented and not profitable for the buyer | *contested*: the refutation concerned a citation and the fit, not the direction. It is used only as a prior on retail P&L, not as a strategy backtest |
| Lou, Polk, Skouras (2019), "A tug of war: Overnight versus intraday expected returns", *JFE* 134(1):192-213 ([10.1016/j.jfineco.2019.03.011](https://doi.org/10.1016/j.jfineco.2019.03.011)); Akbas, Boehmer, Jiang, Koch (2022), "Overnight returns, daytime reversals, and future stock returns", *JFE* 145(3):850-875 ([10.1016/j.jfineco.2021.09.019](https://doi.org/10.1016/j.jfineco.2021.09.019)) | Overnight and intraday legs behave asymmetrically, so a flat multi-session hold mixes two opposing effects | *contested*: the original citation pointed at a secondary summary. Both DOIs resolve in Crossref (metadata checked 2026-09-24); the full texts still need a direct read. Evidence comes from large, liquid names |
| Martineau (2022), *Critical Finance Review* 11:613-646, and the 2025 revival papers | Whether PEAD survives costs is unsettled | *contested*: deferred, not a v3 hypothesis |

Repository evidence points the same way. #162's v1 has **no pass among 768 rule-exits**. All 704 with at least 200
development trades have a negative mean net return. v2 has no pass across its 244 rule-exits (216 E, 16 F, 12 P).
The broad-universe study (`blueprints/us-equities/broad-universe/README.md`) reports that its flags "find
*volatility*, not direction".

The sweep also stated that "squeezes are episodic, not a base rate". Its only source for that is an unverified S3
Partners conference draft (EFMA 2025), not Hong et al., so v3 gives its squeeze test (H5-s) no directional prior.

The literature is monthly, cross-sectional and mostly large-cap. Whether it carries over to catalyst-conditioned
movers priced at $1 to $50 is what v3 tests; it is not an assumed result.

## Hypotheses H1-H6

v3 tests the effect's **sign and conditioning**, not continuation alone. `protocol-draft.json` gives the exact arms,
primary tests, minimum samples and windows. Two populations are common to H1-H5, and both reuse #162's definitions
from `rules.py` by reference:

- **D (daily lane):** a split-consistent close-to-close gain of at least +20%, a price of at least $1 and a
  completed-session dollar volume of at least $1M. The decision is at 16:15 ET, and the entry is the first eligible
  quote at or after 09:35 ET on the next session.
- **I (intraday lane):** the first minute from 09:35 to 10:30 ET at which `gain_at_t >= 0.20` and
  `dollar_volume_at_t >= $1M`, with `price_at_t >= $1`. The entry is the first eligible quote at or after
  decision + 60 s.

The draft restates these formulas exactly, since `rules.py` does not define `ref` or the gain. Official opens and
closes count only from the listing exchange's auction print or official close. A close printed only on another
exchange, or a missing previous close, means no event, with no bar fallback. A session whose raw close ratio sits
within 1% of an integer split ratio with no adjustment is treated as an unadjusted split and is excluded before
membership. Every such case is counted.

H1-H3 use no halt data. As in the catalyst experiment, a halt is never inferred from missing data: fills need an
eligible quote, so a trade set never depends on a later halt-data purchase. Halt state enters only H4.

The sweep's phrase "v1 lanes" mixes two protocols: the catalyst experiment's daily and intraday lanes, and #162's
+20% grid. v3 settles this with D and I above. G = 0.20 and V = $1M are v1's loosest gain and middle volume floor,
chosen for sample size. They were chosen after v1's dev/val results were seen, in which every cell is negative; the
exposure registry records this.

| H | Question | Entry | Exit arms | Sizing | Not supported if | Data |
|---|---|---|---|---|---|---|
| H1 | Does MAX (lottery) conditioning flip the sign? | D and I, with MAX(21 sessions) terciles as a covariate. Breakpoints come from the same population's events in the prior 252 sessions, so they are known at the decision; no new thresholds | (a) exit at min(entry + 30 min, 15:55); (b) the lane horizon (D: 15:55 on the 5th session; I: entry + 60 min); (c) same-session 15:55 | 1x, equal notional, capacity-capped | not supported: at the verdict stage, both high-MAX minus low-MAX tests for arm (b) (D and I) exclude a negative effect of the MDE size, and no H1 arm-by-tercile cell passes. A high-MAX outperformance is outside the one-sided test and supports no claim | **expected available** (Alpaca SIP bars and quotes); 2016-2020 quote and auction coverage is unverified; H1 is tested only if the preregistered coverage rule keeps enough years, decided at the freeze |
| H2 | Do catalyst-verified moves beat pure attention spikes? | D and I, split by an 8-K Item 1.01 accepted before the decision vs a complete, parsed filing index with no qualifying filing; unknown identity or items are excluded from both groups | the lane horizon only | 1x | not supported: at the verdict stage, H2-D and H2-I (catalyst minus attention) are both labelled not supported with the MDE excluded, and no H2 cell passes | **gated**: `catalyst.py` makes every 2016-2020 filing ineligible (availability = max(acceptance, local observation)) and has no Item parser or historical ticker-to-CIK map. Needs a preregistered acceptance-time availability rule, an Item parser, an as-known CIK source and a coverage check before the freeze, else not tested |
| H3 | Do the overnight and intraday legs differ? | D | (a) intraday only: enter at 09:35, exit at 15:55 the same session; (b) overnight only: enter at 15:55 (300 s timeout), exit at the first eligible quote after the next 09:30 open; (c) the 5-session hold split ex post into 4 overnight legs (official close to official open) and 4 intraday legs (official open to official close), comparing mean per-leg returns (a diagnostic, not traded; a trade missing any leg is excluded). Two-sided at development; its direction is then locked | 1x. Arm (b) stays at 1x in any later paper use until the 2x rung and its overnight cap are clean | not supported: at the verdict stage, the per-leg difference excludes the MDE, and neither traded arm passes | **expected available**; 2016-2020 quote and auction coverage is unverified; H3 is tested only if the coverage rule keeps enough years, decided at the freeze |
| H4 | Does a halt-conditional exit beat ignoring the halt? | No new entry. Applies to every D and I lane-horizon (b_lane) trade, deduplicated by symbol, session and entry time, that meets a halt or, for a Nasdaq-listed name, an LULD pause (not only passing arms, so that a no-pass outcome still leaves a sample) | (a) exit at the reopening of the first halt that starts after the entry fill, at the reopening-cross print (source fixed before the freeze) or the first post-reopen quote; (b) hold to the lane horizon. A halt still in force at the planned exit gives both arms the same post-reopen price (difference 0); one that spans a segment end is excluded; a pause folded into the closing cross exits at the official close. No fills during a halt. Both sides costed at the wider of the table and the realized post-reopen spread. Pause length is logged as a covariate, not a signal. Two-sided at development; its direction is then locked | inherits the parent arm | not supported: at the verdict stage, the (a) minus (b) difference excludes the MDE. Below the minimum halted trades it is underpowered. Either way the halt state stays a safety rule only | **gated** (Databento XNAS.ITCH status schema, paid, *contested*: corrected from raw ITCH messages to the normalized schema; Nasdaq Trader history as a short pilot) |
| H5 | Does days-to-cover crowding filter movers? | D split by days-to-cover tercile (short interest / ADV, both in the decision session's share basis; trailing 252-session breakpoints), using the latest FINRA figure published before the decision, with its settlement lag | the lane horizon | 1x; a filter, never a size input | primary (H5-p): high minus low DTC is labelled not supported with a negative effect of the MDE size excluded. Secondary squeeze test (H5-s, no sourced prior): high DTC minus the pooled middle and low terciles, reported separately. Either way at the verdict stage and with no H5 cell passing | **gated** (FINRA short-interest access and terms; history must cover the 2016 warm-up) |
| H6 | Engineering, not alpha, in its own draft and one-test family: do broker-held exits realize exit prices equivalent to client-side exits? | a named mechanics-only strategy at a fixed minimal notional, entering after 10:31 ET only in symbols that are flat, have no open order, are not an I event that session and had no D decision in the previous 5 sessions, assigned to an arm by a hash of symbol, session and entry count written to the ledger before the order is sent. Not yet defined, so H6 cannot accrue | (a) the current `exits.py` chain: client-side triggers, one exit limit, replace disabled (the shipped default); (b) the quantity split into two tranches, each with exactly one broker-held GTC closing order: an OCO (take-profit and a stop-market stop) on the take-profit tranche and a `trailing_stop` (trail_percent from `effective_trailing_bps` at entry) on the rest. Time, risk-off, force and halt exits stay client-side | the strategy's fixed minimal notional | not supported: the median exit slippage of positions whose first exit was stop-type, taken intention to treat to their final close, is not shown equivalent within ±25 bps against each arm's preregistered trigger level and against the NBBO bid at trigger (TOST, 200 per arm per confirmatory stage); or paper partial-fill or trigger behaviour departs from the docs. REST calls per position are reported, not tested: arm (a) needs about 2, arm (b) at least 3 | **gated**: no position source; needs the strategy, a recorded decision on the no-manufactured-trades rule, the adapter change, a paper smoke test and a paper pilot projecting at least 1.5x each stage minimum within 126 sessions (else dropped) |

**Outcome labels.** Each test ends in one of three preregistered labels: a pass; *not supported*, with the excluded
effect size stated; or *underpowered*. A pass is named by its stage: *nominated* at development, *screened* at
validation and *supported (confirmatory)* only at the holdout. Each hypothesis-level verdict names its stage too. At the
minimum samples the detectable effects are roughly 3-26% (the MDE tables in the protocol draft), far above the
literature's roughly 1% a month, so a miss on H1, H2 or H5 will most likely be labelled underpowered. v3 can detect
only large mover-specific effects.

**Data status is fixed at the freeze.** H2, H4 and H5 are each recorded then as tested (data in hand) or not tested
(p = 1 at every stage, permanently). So are H1 and H3: a 2016-2020 year below 90% official-close coverage or 80%
eligible-quote coverage is dropped, and with fewer than 2 development years left, or without 2020, both are not
tested. Data bought or obtained after the freeze can only start a new protocol version,
so it cannot change this family's Holm thresholds after results are seen.

**Exposure and chronology.** Development is 2017-2019 and validation 2020. The holdout is 252 sessions (early closes
included) starting at the 40th session after the freeze commit. If the validation results are not pushed before then,
the holdout of this protocol version is void; there is no deferral, so its start cannot be chosen after the results are
seen. Every holdout trade enters the primary statistic. Paper orders in holdout symbol-sessions are logged at order time
and removed only in a sensitivity, and more than 5% exposed trades labels an item's holdout contaminated. An ad hoc read
of holdout prices voids the holdout rather than removing trades. The 2017-2020 windows are
disjoint from #162's v1 and v2, but not unseen. The broad-universe study computed forward returns for every eligible
symbol-session in 2017-2021 (its C0 control), including a descriptive lane covering names with a close of at least $1,
a median dollar volume of at least $2M, 60 prior contiguous bars and no gap. C0 on that lane is the superset exposure
for most of D and I; its S2 volume-shock signal overlaps D but is not a superset. This plan's author also read its S2
headline for that period. Development and validation are therefore
**screening stages only**: validation decides which items the holdout opens for, and only the prospective holdout can
support a confirmatory claim.

H1 rests on BCW 2011 (**survives**) and the relative-volume/price-return ranking in
`catalyst-experiment/protocol.json`, which is structurally a MAX-like selection. H2 rests on the Barber/Odean line
(*contested*). H3 rests on LPS 2019 and ABJK 2022 (*contested*). A VWAP-loss or ladder arm, from Maróy's SSRN 5095349
(posted 2025-01-12, returned HTTP 403, never read), is **excluded from the confirmatory family**. It can be added only
by an amendment made before the freeze.

H4's mechanics come from the SEC DERA LULD papers
([1](https://www.sec.gov/files/dera-luld-white-paper.pdf),
[2](https://www.sec.gov/files/marketstructure/research/dera_wp_luld_and_extraordinary_transitory_volatility.pdf);
*contested*). The execution-state idea survives. The claimed "pause duration predicts post-reopen volatility" is a
statement from DERA's literature review, not a DERA finding. The rest comes from Nasdaq's LULD material (a 15 s limit
state, a 5-minute pause, and pauses in the last 10 minutes folding into the close; opened by the reviewer, *contested*)
and the [Nasdaq Trader halt pages](https://www.nasdaqtrader.com/trader.aspx?id=TradeHalts) (**survives**; a web/RSS
interface with a limited lookback, not a bulk archive).

H5 rests on Hong et al. (**survives**) for H5-p only. H6 rests on
[orders-at-alpaca](https://docs.alpaca.markets/docs/orders-at-alpaca). `trailing_stop` **survives**. The bracket
proposal was *contested* and corrected to OCO: a bracket's take-profit closes the whole position, so it cannot
express `take_profit_fraction` < 1. The same page limits how legs combine: "Trailing stop orders are currently
supported only with single orders", and "you would not be able to submit two conditional closing orders since
Alpaca's system would view one of the two orders as exceeding the available position quantity". So a share can carry
either a trailing stop or an OCO, never both.

## Data plan

| Need | Source | Status now | Gate |
|---|---|---|---|
| PIT daily and minute SIP bars, quotes, official auction prices, corporate actions (H1-H3, H6) | Alpaca market data (SIP), already entitled; used by `broad-universe` and `extreme-gainer-audit` | bars **available** (daily from 2016-01-04, minute from 2016-01-01); quote and auction-print coverage for 2016-2020 **unverified** | a metadata coverage check before the freeze; private hashed snapshots pinned with their asof date. Before 2020, survivorship is limited (`broad-universe/README.md`), so results for 2017-2019 carry that label |
| 8-K Item 1.01 acceptance times (H2) | SEC EDGAR through the catalyst-provenance and catalyst-dataset recipes | **gated**: `catalyst.py` parses no Item and has no historical ticker-to-CIK map, and its availability rule fails every historical filing | a preregistered acceptance-time availability rule, an Item parser, an as-known CIK source and an index-completeness check, all before the freeze |
| Shares outstanding and public float (screen only) | [SEC XBRL frames](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) | **available** as a screen (*contested*: one misattributed source corrected) | frames give one last-filed value per entity. Each row carries `accn` but no filed date, and superseded vintages are absent. A name that clears the screen must be confirmed from companyfacts (or submissions by `accn`) for the filed date and the original vintage before the float counts as point-in-time |
| Historical halt, LULD and status events (H4, halt fidelity in simulation) | Databento XNAS.ITCH normalized status schema (`databento/dbn`, Apache-2.0; *contested*: corrected from raw ITCH H/h/J messages to the normalized schema), cross-checked against the Nasdaq Trader halt history | **gated on paid data the user must buy** (Databento is metered). A free short-window pilot is possible | get a `Historical.metadata.get_cost` quote for one symbol-year; confirm the coverage start and the licence. Per the TotalView-ITCH 5.0 spec, halt and resume state (H, Q, T) covers every security traded on the Nasdaq execution system, including other exchanges' listings; the LULD pause state (P) and the auction collar (J) are for Nasdaq-listed names only, and a pause in another listing appears as a halt |
| Survivorship-free delisted history before 2020 | Norgate Data US Platinum ([prices](https://norgatedata.com/prices.php); *contested*: facts confirmed, but not new, since it is already named in `catalogs/sota-convergence/manifest-20260923.json`) vs the in-repo SEC Form-25 proxy | **gated on paid data the user must buy** | read the EULA's derived-data terms and what happens when the subscription lapses. Compare only |
| Short interest (H5) | FINRA consolidated short interest (`blueprints/us-equities/acceptance-wave/factors-regimes.md`) | **gated** on access and terms the user must establish | model the publication and settlement lag; a bi-monthly overlay only |
| Order latency and fill agreement | Alpaca paper `trade_updates` timestamps plus `x-ratelimit-*` headers | **available** (paper) | probe orders come out of the 20-call management reserve and are labelled as measurement |
| Earnings surprise (deferred lane) | Benzinga via Alpaca news, or a licensed calendar with revision history | gated on paid data; **not a v3 priority** | PEAD after costs is contested |

## Automatic exits and leverage

**Exits are deterministic and preregistered, and each sits at the cheapest correct layer.**

1. **Broker-held legs handle price triggers where the semantics fit, with at most one closing order per share.**
   Alpaca rejects a second conditional closing order on the same shares, and a `trailing_stop` cannot be an OCO or
   bracket leg (both quoted above). So the position is split into tranches, and each tranche carries exactly one
   broker-held order. The take-profit tranche carries an OCO (stop-loss and take-profit). The rest carries an Alpaca
   `trailing_stop` with `trail_percent`, which replaces the client-side trailing rule and is that tranche's only
   stop. Its percentage is sized from `effective_trailing_bps` at entry and is not changed afterwards. Both tranche
   orders are GTC, so a multi-session hold needs no daily resubmission, and they are sent only once the entry order
   is terminal. A bracket is used only for a new entry whose two legs close the whole position. The docs define these
   order classes, but Alpaca's simulated paper fills for them (partials, trigger price, trigger reference) are
   unmeasured. H6 measures them before anything relies on them.
2. **Client-side rules keep everything that depends on state**, in the existing `exits.py` precedence: force_exit,
   risk_off, quote_stale, stop, take-profit, trailing, time_exit. A market-halt rule is a proposed v3 adapter
   addition; today's `halted` in `native_strategy.py` is the ledger's risk halt, not a trading halt. Gap risk stays in `native_strategy.evaluate_gap_risk`. A
   client-side exit first cancels that position's broker-held legs. Cancel-then-new stays the default because of the
   PATCH-replace fill race already recorded in `blueprints/us-equities/order-contract/README.md`.
3. **The halt state machine runs halted, then reopening auction, then post-auction.** No fills are simulated through
   a halt. Exits are priced at the auction or the first post-reopen print. Only halt-driven exits are exempt from the
   quote-staleness and spread admission checks, never entries. A resting stop on a halted name fills through the gap
   at the first print, not at its stop price.
4. **Kill switch and step-down.** One `DELETE /v2/orders` call cancels every open order
   ([reference](https://docs.alpaca.markets/reference/deleteallorders-1); **survives**). HTTP 207 returns a result
   for each order, and failed entries are reconciled one by one against the durable ledger. Positions are then
   flattened with closing orders, sent only after every cancel is acknowledged as terminal, because shares still
   held for an open order would make a closing order exceed the available quantity. Today `native_adapter.py` cancels in a loop, one call per order (line 391). The
   close-all-positions endpoint was not verified in this sweep.

**Automatic leverage is a ceiling, never a target.** The effective ceiling for new entries is the minimum of:

- `max_leverage` (at most 4);
- the session x regime cell;
- the drawdown-ladder step (`leverage.py`: 4x at 0 drawdown, 2x at 0.25, 1x at 0.5, 0x at 0.75);
- the overnight cap (`OVERNIGHT_MAX` = 2, `INTRADAY_MAX` = 4);
- the kill switch;
- the account multiplier proven at preflight.

This is the `leverage-schedule-v1-20260922` contract in `adaptive-paper/README-safety.md`. The hard caps in
`safety.py` (`max_order_notional_usd`, `max_gross_exposure_usd`) apply whatever the policy says.

Size = inverse-vol weight x liquidity cap x edge shrink, clipped to that ceiling:

- **Liquidity cap:** each order is at most a preregistered fraction of trailing ADV and of recent minute volume. The
  sweep found no ADV term in `strategies_v1.py`.
- **Edge shrink:** 0 until a v3 rule passes its untouched holdout. H6's mechanics-only strategy is exempt because it
  makes no alpha claim; it trades a fixed minimal notional. After that it becomes fractional Kelly, at most
  half, with estimation-error shrinkage (MacLean, Thorp, Ziemba 2010, *Quantitative Finance* 10(7):681-687;
  *contested*: citation only, full text not opened). `cvxgrp/kelly_code` stays `discovery_only` because it is GPL-3.0
  and has not been pushed since 2020.

**Promotion is automatic only inside the gates.** A strategy runs at 1x until it passes. It moves up one rung at a time
(1x, then 2x, then 4x), and only after the rung below completes with `needs_attention == 0` in its row of
[`catalogs/us-equities/gates-20260922.json`](../../../catalogs/us-equities/gates-20260922.json)
(`leverage-ladder-1x`, `-2x` and `-4x`, all `not_established` today). Any of these steps a strategy down one rung
automatically:

- any `needs_attention`;
- any `seconds_above_next_lower_rung_ceiling` breach (`runner.py`);
- a preflight multiplier below the request.

The ladder qualifies the engine, not a strategy. Leverage stays paper-only, and live trading is out of scope. The
FINRA 4210 intraday-margin change is already tracked in `catalogs/us-equities/convergence-program/trading.md` and is
not re-added.

## High-rate execution design

**Throughput is capacity, not a trading target.** `adaptive-paper/README.md` (line 40): "No strategy manufactures
trades to hit a throughput target." For movers, the binding limits are candidate count, liquidity and per-share cost,
not API calls. No design below may add orders to use spare budget.

The execution path:

- **No polling.** Fills and state changes arrive on the `trade_updates` stream. REST reads are for reconciliation
  only, about 3 per minute (account, positions and open orders).
- **Rate limiting.** One client token bucket covers every REST call (submits, cancels, replaces and reads), smoothed
  to about 3 actions/s on the 200 tier and about 15/s on the 1000 tier. Nautilus
  `LiveRiskEngineConfig(max_order_submit_rate, max_order_modify_rate)` is only a subset of it: `build_node` sets two
  separate `180/00:01:00` limits for submits and modifies (`native_adapter.py` lines 462 and 486-487), which together
  allow 360/min, and it throttles no cancel or read; `_cancel_all_orders` (line 391) loops unthrottled. The client
  honours `x-ratelimit-remaining`, `x-ratelimit-reset` and `retry-after`, and backs off on 429.
- **Tier selection.** The higher tier is used only when preflight sees `x-ratelimit-limit` > 200 on the account's
  real endpoint. Paper reports 200 today. Other clients on the account share the quota.

**Cost per API action** (sources: [usage limit](https://alpaca.markets/support/usage-limit-api-calls), the
[staff note](https://forum.alpaca.markets/t/what-constitutes-an-api-call/16502/3) cited in `README-transport.md`, and
[cancel-all](https://docs.alpaca.markets/reference/deleteallorders-1)):

| Action | Calls |
|---|---|
| submit (any order class, including a bracket that creates entry plus two legs) | 1 |
| single cancel | 1 |
| `DELETE /v2/orders` cancel-all, whatever the number of open orders | 1 |
| PATCH replace (not adopted: fill race) | 1 |
| each REST read (account, positions, orders) | 1 |
| broker-held OCO/trailing/bracket leg that later fills or is cancelled by the broker | 0 |

**Completed round trips per minute.** *f* is the entry fill rate. The 200 tier keeps 20 calls for management, leaving
180 order actions. The 1000 tier keeps about 100, leaving 900.

| Pattern | Calls per completed round trip | 200 tier, f = 1 | 200 tier, f = 0.5 | 1000 tier, f = 1 | 1000 tier, f = 0.5 |
|---|---|---|---|---|---|
| DAY limit entry, limit exit, cancel unfilled entries | 2 / f | 90 | 45 | 450 | 225 |
| IOC marketable-limit entry, limit exit (IOC unverified on the adapter) | 1 / f + 1 | 90 | 60 | 450 | 300 |
| bracket (entry plus OCO legs in one POST), legs never changed, cancel unfilled parents | (2 - f) / f | 180 | 60 | 900 | 300 |
| entry, then one `trailing_stop` after the fill | 2 / f | 90 | 45 | 450 | 225 |
| entry plus the current client-side exit (`exits.py` triggers, one exit limit, replace disabled by default) | 2 / f | 90 | 45 | 450 | 225 |
| the same with `exits.replace_enabled`, r re-prices of an unfilled exit (at most 3; r = 3 shown) | 2 / f + 2r | 22 | 18 | 112 | 90 |

The sweep's synthesis gave "2 + (1 - f) / f, about 60 round trips/min at f = 0.5" for the plain limit pattern. That
counts the cancels but leaves out the extra *submits* of unfilled entries. Each attempt costs one submit plus either
a cancel or an exit, so a completed round trip costs 2 / f calls. That is 45 per minute at f = 0.5, not 60.
The 60 belongs to the IOC pattern, where an unfilled entry needs no cancel.

**What cannot be reached.** 1000 round trips per minute on one account needs at least 2000 plain-order calls, or 1000
bracket calls with no cancels, no reads and a 100% fill rate. Both exceed a 1000/min budget. Even 1000 *order
actions* per minute is out of reach once any read or cancel happens.

The **cost check:** 900 actions/min x 100 shares x $0.004/share is $360 a minute, about $140k per 390-minute session if
sustained. Cost and liquidity rule out sustained high rates long before the call budget does.

There are two 1000/min paths, compared but not adopted (*contested* only on decision value):

- [Non-retail](https://alpaca.markets/support/increase-api-rate-limit): 1000/min at $0.004/share, giving up wholesale
  routing.
- [Elite](https://alpaca.markets/elite): 1000/min with a $30k deposit, priced at $0.0040 All-in or $0.0025 and lower
  (Cost Plus).

The Elite DMA gateway is excluded (see Dropped).

**v3 adapter changes this design needs, none of them made here:**

- OCO, bracket and `trailing_stop` order paths in `native_adapter.py` (which builds only LIMIT/DAY orders today);
- batch cancel-all on step-down;
- IOC entries, once IOC is verified;
- an audit of fail-closed handling across *both* vocabularies. The `trade_updates` event names (`calculated`,
  `suspended`, `stopped`, `done_for_day`, `order_replace_rejected`, ...) differ from the order `status` field that
  `transport.py`'s `TERMINAL` set checks.

## Simulation fidelity

- **Engine.** NautilusTrader 2.0.0rc5 backtest (the selected destination) with its native fill and latency models.
  The pinned review of `fill-models.md` and `reconciliation.md` at `27a8e54` is in
  `catalogs/us-equities/architecture/trading.json`.
- **Rate limits in simulation.** The same single client token bucket as paper runs over every REST call, at 180/min
  (or 900/min for the higher-tier scenario); the `LiveRiskEngine` submit and modify throttles run inside it as a
  subset. Every submit, cancel, replace and read uses a simulated token. Going over budget returns a simulated 429
  and a `retry-after` delay, so queueing shows up as worse entry prices.
- **Fills on minute SIP bars, with NBBO where entitled:**
  - a passive limit fills only when the bar trades *through* it, with a queue haircut;
  - a marketable order fills at the far touch plus participation-scaled impact, with participation capped;
    anything over the cap fills partially;
  - there are no fills during halts. Reopens use the auction print, and stops fill through the gap;
  - broker-held legs are simulated with their documented cancel-the-other-leg semantics;
  - the LEAN execution-realism grid (0, 5 and 20 bps plus $1 per order) is the minimum cost-scenario set.
- **Latency.** Calibration follows hftbacktest's documented protocol
  ([Order Latency Data](https://hftbacktest.readthedocs.io/en/latest/tutorials/Order%20Latency%20Data.html);
  *contested* only as a new-row proposal, and kept as a note on the existing row). Submit, ack and fill/cancel
  latencies are measured from `trade_updates` during normal paper operation. At most 2 unfillable far-from-mid probes
  per minute may be added from the management reserve, labelled as measurement and never as trades. Whether probes
  comply with the no-manufactured-trades rule needs an explicit decision (see Open questions). hftbacktest itself
  (MIT, catalogued at `5f3ec40`, no push since 2025-12-23) stays a comparison harness on a tick subset only.
- **Sim-to-paper agreement.** The same decisions are replayed in simulation and on paper, with preregistered
  thresholds for:
  - fill rate per order type (binomial CI);
  - slippage vs arrival mid (median and p90, paper minus sim);
  - latency (two-sample KS);
  - an exit-reason confusion matrix;
  - P&L tracking error;
  - 429 and throttle-delay counts.

  Size starts minimal, and the fill model widens only while agreement holds. **Alpaca paper fills are themselves
  simulated** and do not simulate `advanced_instructions`. This measures sim-to-paper agreement, not sim-to-market
  agreement. A high-rate capacity replay is an infrastructure test, never strategy evidence.

## Catalog decisions

The sweep's catalog actions are dated records in
[`catalogs/us-equities/mover-v3-sweep-20260924.json`](../../../catalogs/us-equities/mover-v3-sweep-20260924.json):

- **Registered with the decision index** (`python3 scripts/catalog_decisions.py --write --supplement
  catalogs/us-equities/mover-v3-sweep-20260924.json#/repository_decisions`): every record that names a GitHub
  repository (`alpacahq/alpaca-py`, `databento/dbn`, `nkaz001/hftbacktest`, `cvxgrp/kelly_code`,
  `microsoft/RD-Agent`, `microsoft/qlib`, `polakowo/vectorbt`, `mementum/backtrader`), with one intentional
  exception below. Every registered repository was already in the union, so the repository count is unchanged.
- **Intentionally not registered:** the no-change record for `VladPetrariu/Qullamaggie-breakout-scanner`. The scanner
  is absent from the union, and registering a duplicate that is not adopted would add a new identity to the grand
  union and to the token-native saturation audit's identity partition, for no decision value. The record stays in
  `/non_repository_decisions` so the next sweep still finds it.
- **Kept as data in the same file** (`/non_repository_decisions`): papers, broker APIs, SEC/Nasdaq pages and data
  vendors. The union accepts only repository records.

Inclusion never upgrades evidence. Each record carries its sweep status and its evidence level: literature source
review, metadata, or an unpinned source read. None records native execution.

## Dropped

Killed by verification:

| Item | Reason |
|---|---|
| intraday-volume-imbalance-cross-section | primary source misattributed (Heston, Korajczyk, Sadka is about return periodicity); the U-shape evidence is from index futures |
| fda-catalyst-timing-profile | journal misreported; effects are small on average. A possible future lane, not v3 |
| nautilus-halt-status-model (as a v3 candidate) | background only; halts remain a data-provider responsibility |
| event-study-tooling-gap | the search excluded notebook repositories, so the claimed negative result is unreliable |
| backtrader-family-closed | duplicates the catalog |
| p3-atr-chandelier-stop | `volatility_bps` is not an ATR approximation, and the catalog-status claim was false |
| p8-finra-4210 flag | already catalogued with stronger evidence (`convergence-program/trading.md`) |
| replace-order-patch-semantics | already in `order-contract/README.md` |

Contested items not carried forward. For each, the synthesis judged the refutation strong, or the item was folded
into another:

| Item | Reason |
|---|---|
| p4-massive-flat-files | the repository does not scan one symbol at a time, so it has no decision value |
| p5-iex-hist | a single venue; not an execution-design input |
| dma-gateway-elite-only | Elite-only and cannot be simulated in paper, so not actionable |
| trade-updates-full-event-taxonomy (as stated) | conflated event names with status values; replaced by the fail-closed audit above |
| order-action-budget-arithmetic (as a catalog artifact) | a duplicate; its arithmetic (corrected) is used directly in the table above |
| pead-cost-adjusted-contested (as a v3 hypothesis) | wrong journal cited (pii S0148619524000584 is the *Journal of Economics and Business*); the evidence is unsettled |
| p6-oto-single-leg-order | folded into the OCO/trailing path; the savings are marginal |
| qullamaggie-breakout-scanner (as a new entry) | duplicates the catalogued `tradermonty/claude-trading-skills` vcp-screener; recorded as no-change (not registered; see Catalog decisions) |

## Open questions

- Do Alpaca paper fills for `trailing_stop`, OCO and bracket orders (partials, trigger price, trigger reference) match
  the docs? H6 depends on it.
- Does paper `x-ratelimit-limit` ever show an upgraded tier, and can a higher tier be qualified in paper at all?
- Are IOC and FOK supported on the Nautilus/`native_adapter` path, and are IOC semantics in Alpaca paper documented?
- Can SIP trade and quote conditions rebuild historical halts and LULD states? XNAS.ITCH carries halt state for every
  Nasdaq-traded security but distinguishes an LULD pause only for Nasdaq-listed names. Is another venue's feed needed
  to separate pauses from halts in NYSE-listed names, or is H4's pause stratum restricted to Nasdaq listings? What are
  the cost and the coverage start?
- Should v3 add a short side for the MAX-reversal prior? Borrow, hard-to-borrow fees and SEC Rule 201 were not
  examined.
- Do latency probes (unfillable, then cancelled) comply with the engine's no-manufactured-trades rule? This needs an
  explicit decision. The same decision is needed for H6's mechanics-only strategy; if the answer is no, H6 is dropped.
- What are the terms of FINRA short-interest access and of the Norgate EULA on derived data?
- The citations that need a direct read before exact wording is cited: the LPS 2019 and ABJK 2022 DOIs, SSRN 5095349
  and the full MacLean-Thorp-Ziemba text.

## Before any freeze

`protocol-draft.json` lists the preconditions (`freeze_preconditions`). The main ones:

- an independent pre-outcome review, from a different session and model family, with every finding resolved in a
  dated record;
- the direct citation reads above, or removal of the claims that depend on them;
- the 2017-2019 cost re-measure fixed by rule only; it runs as the first step after the freeze, because its quote
  stamps coincide with outcome prices; fee rates dated for 2017-2020;
- metadata-only coverage checks, run only by committed count-only code that emits counts and rates and seals the raw
  pages unopened: 2016-2020 official prints by source label, quotes at non-v3 coverage stamps, split and dividend
  records and suspected unadjusted splits (H1-H3); H2's identity and filing-index gates, H4's halt and reopening-print
  sources, H5's short-interest history including the 2016 warm-up;
- the v3 session calendar and fee file pinned;
- H1 and H3 (by the coverage rule) and H2, H4 and H5 each recorded as tested or permanently not tested;
- the universe and daily-dataset snapshot pinned with its asof date;
- study code committed with synthetic tests before any outcome is computed, including split and ex-dividend
  crossings, early-close sessions and segment-end censoring.

H6 has its own preconditions in `h6-execution-parity-draft.json`, including a named mechanics-only strategy, a test
that one share never carries two closing orders and a paper smoke test of the tranche pair.

The second and third review rounds' findings and their resolution are recorded in `protocol-draft.json`
(`review_record`).

Until all of that is done, this is a plan, and no window it names may be read for outcomes.
