# Adaptive paper heartbeat — September 23, 2026

Two native SIP paper attempts stopped before the authorized five-minute window completed. They submitted **zero orders**, received **zero fills**, and completed **zero roundtrips**. Both reconciled with zero positions, zero open orders and a $0.00 cash difference. The explicit recovery completed at 14:05:52 UTC; that cleanup success does not qualify either entry attempt.

The [machine-readable receipt](heartbeat-20260923.json) preserves both outcomes, source identities, counts and artifact hashes. The September 21 synthetic capacity and one-SPY broker smoke remain separate historical evidence. Actual adaptive throughput, profitable strategies and all-family native execution are unqualified.

## Account and risk continuity

The existing account ledger and lock were reused. A separate one-shot 10:05 Eastern timer, configured by another task to create a new state root, was stopped before execution. The periodic heartbeat remains active.

The exact previous SIP configuration was recovered and independently verified: SHA256 `77244c396c407d20f7b21f0e9e8ad9a2c4803ad663247ac210076a47ebbc7eb3`. Its capital $10,000, gross exposure $5,000, order $1,000/one share, loss/drawdown $25, 1x leverage, 300-second duration, 120-second cleanup, shared 200 REST/minute and 180 all-submissions/minute ceilings remain unchanged. Extended hours, overnight holds, rotation, gap-stop and exit replacement are not enabled by this configuration.

Current source had added two default risk fields which the old ledger could not recognize. The reviewed compatibility change accepts only the complete exact legacy canonical limits with those new fields at their original fixed/1 defaults. It updates metadata atomically without resetting history. Ledger requests increased from 60 to 168; all 108 new ledger-accounted calls were reads, with a peak of 36 in any rolling 60 seconds. Three trial records remain, including the prior trial. There are no intents or owned positions.

## Native attempts and diagnosis

| Attempt | Source | Elapsed | Raw status | Assessment |
| --- | --- | ---: | --- | --- |
| First | 507373b | 14.203 seconds | completed_no_signals | Premature stop before warmup; five-minute acceptance rejected |
| Diagnostic | 1e2c96a9c7f8f637890eda65ec144324c3dd63e9 | 2.774 seconds | needs_attention | Transport gap; quote normalization raised TransportError |

The first trigger was not recorded. The reviewed reporting fix records the decision-loop exit and pre-shutdown health, preserves abnormal failure status even after flat cleanup, and records shutdown timeout/cancellation separately. It does not change quote validation, risk or order behavior. Both frozen runtime trees matched their committed bytes and were made read-only before execution.

The diagnostic attempt authenticated both streams and received 3,208 native quotes before the guard stopped it. The recorded callback failure occurred in quote normalization. A separate 15.023-second read-only SDK sample at 14:07:10–14:07:25 UTC received 19,438 SIP quotes: 19,405 passed normalization and 33 had bid above ask (31 QQQ, two AVGO). All 33 failed the existing executable-quote check; none had nonpositive prices. This proves crossed quotes occur in the current feed, but does not identify the exact raw quote that stopped either trial. No raw quote payloads were retained in the probe output.

[Alpaca's quote schema](https://docs.alpaca.markets/us/docs/real-time-stock-pricing-data) defines bid, ask, size, timestamp and conditions. The bounded probe reused the installed official [StockDataStream](https://alpaca.markets/sdks/python/api_reference/data/stock/live.html). A condition code by itself does not establish executability.

## Research and strategy scope

The bounded IEX research snapshot at 13:37:39.732776 UTC collected 50 news items and 24 market snapshots, with no collection errors. All 50 article IDs differed from the September 21 collection; the capped window still reports more items available. Publication, update and observation times remain separate in the private research artifact. Catalyst rankings remain advisory and cannot generate orders.

Twenty-three quotes were fresh; six were both fresh and within 15 basis points. Benchmark prior-close changes were SPY -0.144%, QQQ -0.306%, IWM -0.857% and DIA -0.206%; breadth was eight positive and sixteen negative symbols. These are snapshot-to-prior-close comparisons, not returns since the earlier research collection. The IEX observation is separate from native SIP execution.

Trend momentum, range breakout, mean reversion and relative strength require their actual rolling windows and executable quotes; this snapshot establishes none of them. Defensive cash remains an available policy, but both short attempts stopped before a policy family was selected. No strategy profitability or market-following claim follows from these observations.

SIP ingestion at 13:42:53 UTC returned 480 daily bars for 24 symbols over 20 completed sessions through September 22. The promotion gate passed all 12 checks at 13:43:10.762061 UTC. This validates the bounded data input, not quote-stream behavior or strategy alpha.

## Verification and next acceptance

The baseline suite ran 498 tests with one existing skip. Legacy-ledger compatibility ran 502 with one skip, plus 53 independent safety tests. The first diagnostic patch ran 512 with one skip; independent review passed nine stop-status, 78 runner and 49 transport tests.

Native Claude reviewed the source and found no blocking status defect. Its diagnostic concerns were resolved in worker commit `6d7bc8ad218fbd2971b3498082aecebe4364f314`, integrated as `88b5444`: fixed rejection codes distinguish crossed and malformed quotes without recording raw payloads; cleanup exceptions retain the stop context; a serious transport failure during final reconciliation cannot claim success. The late-health hypothesis was reproduced before correction. This follow-up ran 518 tests with one skip, plus 138 independent checks (nine native StopLifecycle, 51 transport and 78 runner tests), with no remaining supported findings. The native lifecycle tests actually executed; the only skip was the separate optional exchange_calendars comparison. These final source changes were tested offline and were not used in another broker entry trial.

An independent evidence audit matched the native attempt, recovery, news and quote-probe claims and checked retained artifact hashes. The machine-readable receipt records review scope and native Claude usage. Publication integrity, catalog, foundation, convergence, explorer and dashboard checks are retained in the coordinator's task record.

Do not repeat an unchanged entry trial. The next qualification is explicit crossed-quote handling across transport, controller, native quote caches and the order boundary:

- Invalidate executable quotes atomically, retain event-time watermarks, and reject older or equal-time recovery updates. Keep malformed records, unknown symbols, order errors and queue loss fatal.
- Preserve last valid ledger valuations; missing marks must not hide unrealized losses. Block new admissions while held symbols lack valid executable marks.
- Recheck invalidation before POST. Reserved-unsent, already-sent, ambiguous and partially filled orders need distinct ownership, cancellation and reconciliation behavior.
- Test good/crossed/newer-good sequences, stale cache and native tick replays, pending-submit races, held marks, benchmark gating and missing recovery by the deadline. Keep the current risk and warmup limits.
- Obtain native Claude/Codex review and relevant checks before one further five-minute trial on the same account ledger and exact configuration.

The existing whole-feed guard remains in force while this handling is unqualified. No live endpoint, paid feature, additional leverage or catalyst-order signal was enabled.
