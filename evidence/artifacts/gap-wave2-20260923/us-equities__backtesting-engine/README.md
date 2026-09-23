# Gap wave 2: us-equities / backtesting-engine (2026-09-23)

Eight open gaps from the crosswalk (main 92bb279, PR #85) were taken from the unit
list, copied verbatim into [`inputs/gaps.json`](inputs/gaps.json). All expectations and criteria
were preregistered in [`preregistration.json`](preregistration.json), committed in
`2b93d4d` (written 06:21:22Z) before any check ran. A fix round followed an independent
read-only Codex review. Its expectations are in
[`preregistration-fix1.json`](preregistration-fix1.json), committed in `43a2f90`
(written 07:00:03Z) before the fix-round runs. A Codex re-review then found that fill
instants were compared only to whole seconds. A second round, preregistered in
[`preregistration-fix2.json`](preregistration-fix2.json) (`e1fa1b3`, 07:09:27Z), switched
to exact-nanosecond comparison and reran the replay with identical results. Each affected
receipt carries `fix_round_1` and `fix_round_2` blocks. [`results.json`](results.json) is
generated from the receipts by
[`build_receipts.py`](../../../../blueprints/gap-wave2-20260923/us-equities__backtesting-engine/build_receipts.py).
Raw outputs cited by receipts are in [`raw/`](raw/) with host paths replaced by `$HOME`;
each receipt lists their sha256 values.

| Gap | Outcome | Evidence | Receipt |
| ---: | --- | --- | --- |
| 0 | covered_elsewhere | source_review | [SPY/LEAN parity stress mappings](0-spy-lean-parity-peer.json): peer `sota-workflow-resolution` owns the `spy-lean-parity` and `dividend-sim-module` gates |
| 1 | advanced | local_integration | [Nautilus on Alpaca bars across a dividend and a split](1-nautilus-alpaca-bars-corporate-actions.json) |
| 2 | settled | native_proven | [latest non-prerelease Nautilus release](2-nautilus-latest-stable-release.json) |
| 4 | advanced | local_integration | [LEAN oracle under the Alpaca brokerage model](4-lean-oracle-alpaca-brokerage-model.json) |
| 6 | settled | local_integration | [all comparator modes plus the retained review count](6-comparator-modes-and-review-count.json) |
| 7 | covered_elsewhere | source_review | [one_zero distributions and fill rule](7-one-zero-distributions-fill-rule-peer.json): owned by the peer |
| 8 | advanced | local_integration | [AAPL action-window replay with reconciliation](8-aapl-action-window-replay.json) |
| 9 | covered_elsewhere | source_review | [stress and margin parity cases](9-stress-margin-adaptive-parity-peer.json): owned by the peer |

## Measured findings

* **Given raw bars, Nautilus 2.0.0rc5 made no corporate-action adjustment (gaps 1 and 8).** A native
  backtest ran over the 25 retained, hash-verified Alpaca AAPL daily raw bars
  (2020-08-03 to 2020-09-04). It bought 10 shares at the 435.75 close and sold 10 at the 120.96 close.
  The position stayed at 10 through the 2020-08-31 4:1 split, and no cash was posted for the
  0.82 USD dividend (ex-date 08-07, paid 08-13). The native ledger matches a fills-only
  ledger exactly: 96,852.10 USD and a realized PnL of -3,147.90. That is 3,637.00 USD below
  the split- and dividend-adjusted economic reference: 3,628.80 comes from the missing split
  adjustment and 8.20 from the unposted dividend.
  A synthetic probe confirms that the reconciliation catches a dividend credit, a split
  quantity change and a fill stamped 1 ms off its bar instant. The rc5 stubs expose no dividend or split data type that could be fed
  to the engine, so this shows the engine makes no adjustment by itself. It does not show that every
  custom route is impossible.
  The upstream tree at pin `1b0a49d` contains no equity backtest example, and the rc5 stubs
  expose no split or dividend data type. So the "unchanged upstream example" arm cannot
  be met at this pin, and quote-based fills still need a new authenticated Alpaca quote
  acquisition.
* **The Alpaca brokerage model rejects the frozen LEAN oracle's orders (gap 4).** One added
  line, `SetBrokerageModel(BrokerageName.Alpaca, AccountType.Margin)`, made every
  entry order Invalid in five of the six cases. Each submits a MarketOnOpen order at the 16:00 bar,
  outside Alpaca's 19:00 to 09:28 MOO window. The algorithm then failed its lifecycle
  check. `over_limit` failed buying-power validation first, as in the control run. The unchanged
  control run reproduced all six retained end equities. A fix-round rerun with argv recording
  reproduced every exit code, ledger and outcome. Initializing the Alpaca adapter against
  paper endpoints requires broker contact, so that step is deferred to the peer.
* **Every comparator mode now has retained evidence (gap 6).** A fresh bwrap replay was followed by
  runs in `--bars`, `--lean-data` and no-evidence modes. Together they reproduced the harness README's
  table. The two complete modes wrote verdicts byte-identical to the committed `verdict.json`;
  the incomplete no-evidence verdict differs by design. A tampered `--bars` file was refused.
  The mode-independent acceptance suites also passed: 92 and 8 tests. The verdict line was
  recorded for every mode. The 21-of-24 review count is now retained as a verbatim
  agent-lab excerpt, and the spy-parity README points to it.
* **Latest stable release (gap 2).** On 2026-09-23 the latest non-prerelease was still v1.231.0,
  published 2026-08-02. 2.0.0rc5 remains a prerelease.

## Boundaries

No broker, paper-account, credential, gate-row or ledger file was touched. The LEAN and
Nautilus runs were offline inside bwrap, with a new empty network namespace and a cleared environment. LEAN
logs have the machine hostname replaced by `$HOSTNAME`. Private
outputs are under `$HOME/.cache/gap-wave2-20260923/backtesting-engine/`. Network use was
limited to `gh` read calls: the release list, a release view, the upstream tree listing and one
upstream doc file of about 5 KB. Nothing was downloaded or installed.
