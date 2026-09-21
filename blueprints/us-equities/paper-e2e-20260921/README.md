# Alpaca paper E2E and native equity replay — September 21, 2026

The first bounded Alpaca paper roundtrip completed and reconciled: one SPY bought at **$770.70**, then sold at **$770.62**, for **-$0.08**. A fresh read-only SDK process confirmed both complete fills, the exact cash change, zero positions and zero open orders. A new recovery process then adopted the same completed identities with **zero additional order writes**.

The [native paper receipt](paper-receipt.json) records actual timestamps, source/config hashes, numeric limits and verification boundaries. The [runner and operator instructions](../alpaca-paper/README.md) describe the fixed trial, journal, kill switch and recovery. Credentials remain in the existing private environment; the code hardcodes the paper endpoint. No purchase, account reset, live order or paid upgrade occurred.

## What passed

- [Readiness](readiness.json): fresh active/unrestricted paper account, flat/idle state, SPY asset/session and IEX quote; five selected unchanged upstream `alpaca-py==0.44.0` tests passed against the real paper endpoint.
- [Native Claude review](claude-review.json): reviewed the existing foundation and actual installed SDK source. Identified default POST retries, missing transport timeouts and additional numeric/freshness prerequisites. Those supported findings were addressed before execution.
- Independent source review: **27 synthetic lifecycle tests passed**, including uncertain submit, partial-fill/cancel races, duplicate/restart behavior, endpoint/timeout controls and kill switch. The reviewer found and verified the fix for a known-order lookup-gap cancellation defect.
- Native operational trial: two actual paper submissions and full fills; separate cash/order/position reconciliation; completed-trial recovery without resubmission.
- [Native AAPL diagnostic replay](../engine-nautilus/equity-replay/README.md): two engine scenarios on retained authenticated bars, five closed roundtrips each. Baseline **-$133.40**; fee/slippage case **-$144.40**, including $10 commissions and $1 adverse slippage. Eight local oracle/admission tests and independent CSV accounting review passed. Repeated engine runs are reproducibility checks, not additional independent market samples.

## Rate and promotion boundary

All observed account rate headers reported **200 Trading API calls/minute**. The frozen runner uses **120 requests/minute**, one-share SPY, USD 1,000 order/exposure caps and at most four write attempts. [Alpaca Elite](https://alpaca.markets/elite) advertises 1,000 API calls/minute for Smart Router; this does not mean 1,000 completed trades or fills, and this account did not return that entitlement.

The [dated catalog review](../../../catalogs/us-equities/paper-practice-20260921.md) records official SDK/skills/CLI/MCP alternatives and why the existing selected runtime was extended. The [runtime target](../../../catalogs/us-equities/runtime-target.json) and grand dashboard checkpoint distinguish the newly measured paper/simulation scope from remaining work.

Broader catalyst strategy merit, the retained SPY/LEAN corporate-action oracle, realistic finite-liquidity/latency testing, native broker fault injection, streaming reconciliation and IBKR acceptance remain open. Paper execution and completed-trial recovery do not establish those capabilities or profitable live trading. The finite smoke trial has ended; no continuous trading service was started.
