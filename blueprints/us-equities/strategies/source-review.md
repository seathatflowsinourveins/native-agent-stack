# T22 sources and corrections, 2026-10-09

The ten §6 families and three preset columns are untested hypotheses beside the
frozen #16 study. The scope record is us-equities-trading #25 at
`b0994749ca6c52ad07cb3bb70e8b5b6cd4fac910`, read through `git show` after fetching
the PR head. No rank rows, labels or study arms are inputs to these classes.

The landed amendment, us-equities-trading #47 at
`2e0860ccd1d485593d1bd31b8a97c12198ca6b3d`, supersedes exit/scope assumptions:
`docs/decisions/2026-10-09-equities-intraday-scope.md` D1/D2 and the T22 re-plan.
It keeps equity families, pauses option-order families without deleting their
references, and treats exit timing as a versioned parameter measured in research.
All four timing candidates remain untested; none is selected by these fixtures.
The options-flow-to-stock family remains equity-only and OD3-gated.

The timing implementation reuses adaptive-paper's existing session helpers and
`gerrymanoim/exchange_calendars@dbe38b1f6887434bbdd1a7d2df6ff8f1742a048a`
(4.13.2): native XNYS `session_open`, `session_close` and `date_to_session`.
The mirror HEAD was re-verified for this change; no calendar, classifier, engine
or adapter is rebuilt or forked. Nautilus's pinned native `Equity` instrument
type supplies the order-asset gate, rather than inferring it from a symbol or
an option underlying's EQUITY asset class.

T15 owns the shared rich exit disposition and session/adapter capability seam.
Its current #940 interface has ExitContext session/bid/ask and ExitDecision
submit/flag_position/price_rule/limit_price. T22 will bind that accepted interface
at its CC-cued final rebase after #940. Until session support and acceptance,
an overnight research candidate holds and flags at execution. It is not a
blanket-refused candidate or an implicit permission to submit overnight orders.

The requested upstream mirrors were inspected read-only and their native Git
HEADs and clean trees verified. None of the inspected sources ships the complete
Nautilus family/preset interface. This is the demonstrated gap: original family
predicates over available factor observations, configured through registered
presets, with upstream engine callbacks. The engine, market calendar, exit chain,
fill models, latency model, broker transport and request governor are reused.

| Source | Exact pin | Inspected files and disposition |
| --- | --- | --- |
| [nautechsystems/nautilus_trader](https://github.com/nautechsystems/nautilus_trader) | `1b0a49d2792a9432a3aca3fcb617ce7a630d905e`, version `2.0.0rc5` | `python/pyproject.toml`; `python/nautilus_trader/{trading,common,execution,backtest}/__init__.pyi`; `python/tests/unit/backtest/test_backtest_engine_{surface,custom_data,default_ids}.py`; `crates/model/src/data/custom.rs`. Selected native engine, unchanged wheel. |
| Nautilus regression candidate | `7b766f8825b2539c5b2ac1375e9d97b41c509edb`, version `2.0.0rc6` | `python/pyproject.toml`, same APIs. T13 owns candidate acceptance; this lane retains rc5. Shallow mirrors have no local tag refs; versions are verified in source. |
| [tradermonty/claude-trading-skills](https://github.com/tradermonty/claude-trading-skills) | `eab8d5cb97b9982d915944cdaa2df972fa396b22`, MIT | `skills/stockbee-episodic-pivot-analyzer/references/ep_methodology.md`; `breakout-trade-planner/references/minervini_entry_rules.md`; `stockbee-momentum-burst-screener/references/{momentum_burst_methodology,entry_exit_rules}.md`; `vcp-screener/references/vcp_methodology.md`; `position-sizer/references/sizing_methodologies.md`; PEAD screener references. Isolated candidate install, own checks and inverses are required. |
| [paperswithbacktest/awesome-systematic-trading](https://github.com/paperswithbacktest/awesome-systematic-trading) | `ddfee8bb548bd6914191cb8fdb695d533ae16b0d`, no top-level licence | `static/strategies/{short-interest-effect-long-short-version,earnings-announcement-premium,trend-following-effect-in-stocks,short-term-reversal-in-stocks}.py`; conceptual source review only. No source copied. Classes use LEAN `QCAlgorithm`. |
| [alpacahq/gamma-scalping](https://github.com/alpacahq/gamma-scalping) | `c80b5e36f4b375b2c096d1370f6d5962f5abb630`, MIT | `README.md`, `strategy/hedging_strategy.py`: option-delta hedging using Alpaca and asyncio. Adjacent architecture, not stock options-flow entry evidence. |
| [alpacahq/options-wheel](https://github.com/alpacahq/options-wheel) | `3698429289065ceb0c13ffcdc31a966c576779ad`, Apache-2.0 | `README.md`, `core/strategy.py`: option selection and wheel orchestration. Adjacent only. |
| [PyneSys/pynecore](https://github.com/PyneSys/pynecore) | `2adbab448ad8f7349706ba4a2f5f9d34ea726496`, version `6.10.8`, Apache-2.0 | `docs/reference/lib/strategy.md`: Pine-compatible decorator/runtime; T16 owns parity, not a replacement for Nautilus. |
| [Lumiwealth/lumibot](https://github.com/Lumiwealth/lumibot) | `862504052407df2586122b752a645f88ce87afa1`, GPL-3.0 | `lumibot/example_strategies/{stock_momentum,stock_bracket,stock_limit_and_trailing_stops}.py`: Lumibot classes, reference only here. |
| [stefan-jansen/alphalens-reloaded](https://github.com/stefan-jansen/alphalens-reloaded) | `97e8389f9cb0e28a01b6d7024194af5cf614e4e1`, version `0.4.5`, Apache-2.0 | `src/alphalens/performance.py`: diagnostics; T21 owns adoption. No execution Strategy implementation. |
| [cvxgrp/cvxportfolio](https://github.com/cvxgrp/cvxportfolio) | `b3f9d75fd6cc4ee42f8f4e918e2532ce3e429b3d`, version `1.5.1`, GPL-3.0 | `examples/paper_examples/rank_and_spo.py`, policy interface: portfolio optimization, reference only here. |
| [polakowo/vectorbt](https://github.com/polakowo/vectorbt) | `f0d2afba7af8a6e6c1b02afde27c9a16413e86ff`, version `1.1.2`, Apache-2.0 plus Commons Clause | New TCC dispatch at 20:03:51Z: `vectorbt[rust]` for fast sweeps. README's published wheel route, `pyproject.toml` exact Rust extra, `.github/workflows/tests.yml` and unchanged `tests/test_engine.py` engine/portfolio parity and inverse checks. Isolated candidate, never the rc5 strategy order path. |

The owner later removed licence as an adoption gate in this private environment
(co-op direction recorded 2026-10-09T19:46:28Z). The source licences above remain
recorded. That permission does not establish a need to copy or replace an engine.
This implementation continues to use conceptual AST references and no GPL source.

The subsequent vectorbt dispatch adds a shared T13/T22 adoption receipt. T13
assigned the one acceptance run to T22 to avoid duplicated heavy jobs. The exact
1.1.2 PyPI releases and vendor tag SHA were checked directly; the initial mirror
manifest did not yet include vectorbt, so its pin/path question was routed. A
separate candidate environment installs the published precompiled Rust wheel;
the source checkout is used only for unchanged vendor tests. Any future sweep
survivor must be re-tested through Nautilus with T13. This work runs no strategy
sweep and cites no candidate performance.

## Corrections to the draft's reference claims

- The AST short-interest concept is long low short interest and short high short
  interest. The squeeze family is explicitly the opposite-sign, long-only
  hypothesis. The AST example uses `SHORTVOLUME` in its Quandl data class; that
  plumbing is not accepted as outstanding short-interest measurement.
- AST `earnings-announcement-premium.py` describes monthly volume concentration
  and expected announcers, not post-earnings drift. The T22 event/gap/volume
  predicate is simplified event momentum. It is not a reproduction of that file.
- AST trend uses all-time closing highs and a ten-period ATR trailing rule. The
  high flag and ATR are supplied from previously known upstream-derived inputs.
  Preset ATR bands are separate hypotheses, not a claim to reproduce the paper.
- AST reversal is a weekly long-short portfolio. T22's five-session long-only
  control is a deliberate variant. No unlicensed implementation was copied.
- Generic CTS breakout and VCP references do not implement a complete premarket,
  float-normalization or halt-reopen strategy. Numeric gates in registry.json are
  newly registered hypotheses. Missing fields suppress entry.

## Published references

- Boehmer, Huszar and Jordan, *The Good News in Short Interest*, SSRN record
  (2009), [DOI 10.2139/ssrn.1405511](https://doi.org/10.2139/ssrn.1405511).
- Frazzini and Lamont, *The Earnings Announcement Premium and Trading Volume*,
  NBER Working Paper 13090 (2007), [DOI 10.3386/w13090](https://www.nber.org/papers/w13090).
- Bernard and Thomas, *Post-Earnings-Announcement Drift: Delayed Price Response
  or Risk Premium?*, Journal of Accounting Research 27 (1989),
  [DOI 10.2307/2491062](https://doi.org/10.2307/2491062).
- Wilcox and Crittenden, *Does Trend Following Work on Stocks*,
  [source-linked publication](https://www.cis.upenn.edu/~mkearns/finread/trend.pdf).
- de Groot, Huij and Zhou, *Another Look at Trading Costs and Short-Term Reversal
  Profits*, SSRN record (2011), [DOI 10.2139/ssrn.1605049](https://doi.org/10.2139/ssrn.1605049).

Publication identifiers are bibliographic leads; Crossref records were checked,
the primary NBER page was retrieved, SSRN returned HTTP 403, and the trend PDF
was not parsed. The predicates are hypotheses, not paper replications.

## Execution choice and overturn condition

The existing adaptive-paper adapter supports simple LIMIT/DAY and rejects
replacement. T15 owns native advanced-order contract/adapter qualification.
`code-managed-limit-v1` is therefore separately registered, and the target
advanced-order profile refuses without submitting. The simple profile reuses
`exits.py` and sends fresh-quote limit exits in PRE/POST as R9 requires. A resting
order is canceled and replaced only after native terminal confirmation; a halt
suspends repricing. The paper governor still budgets all actual requests.

This choice is replaced when T15 exposes an accepted capability interface and
same-input simulations plus hana's review show the target plans behave through
the native adapter. Portability of the Strategy class does not itself qualify
paper adoption, broker order types or overnight sessions. Historical Layer 1.5
E2E, LEAN strategy-matrix reconciliation, cost/delay sensitivity and T16 Pine
parity remain distinct gates. No strategy performance number is cited here.

## Review correction at 216bed68

The TCC's three P2 findings were reproduced against the reviewed head. The
unclassified vectorbt pytest expression is now under `pytest_k_expression`, and
its actual adoption disposition is classified as a withheld label in the
existing blind-export vocabulary. No test or export policy was relaxed.

The same-family registration reproduction raised rc5's native already-registered
error; identical specs at two engine times also generated different default
client IDs. At `nautilus_trader@1b0a49d2`,
`crates/system/src/trader.rs:566-578` checks the configured StrategyId's final tag,
and `OrderFactory.limit` accepts an explicit `ClientOrderId`. T22 now derives the
ID/tag from family, preset, explicit stable instance, instrument, profile and
cohort, and restores its seven-digit client sequence from the existing durable
ledger's maximum matching intent, following `native_strategy.py:102-104` and
`:1018-1026`. Dirty ledger/cache startup refuses entry; a prior terminal entry
attempt remains consumed. The wire governor retains reserve-before-send.

The new native regressions exercise four instances in one engine and one real
LiveNode, fixed IDs under a shifted engine clock, maximum-sequence restoration,
unresolved/position refusal and a real synthetic ambiguous LiveNode submit,
followed by closing/reopening the SQLite ledger and proving no new submission.
Supplying the ledger also exposed rc5's PyO3 allocator keyword boundary; a thin
subclass `__new__` now leaves Python-only dependencies for `__init__`. Both
repository generators rerun in the unchanged T13 rc5 environment, with no native
test skips. Overnight paper/session qualification remains a disclosed boundary.

## Lifecycle correction at 93871505

The earlier matrix could finish a synthetic position while still issuing an
invalid early cancel. A native regression reproduces that cancel at the forced
exit's submission nanosecond, before its four-second timeout. The corrected
pending branch applies deadline cancellation to entries and non-forced exits;
an already-forced time exit observes its normal timeout and can fill once.

The pinned source for cancel-by-ID and cancel-reject dispatch is
`nautechsystems/nautilus_trader@1b0a49d2792a9432a3aca3fcb617ce7a630d905e`,
`crates/trading/src/python/strategy.rs` (`py_cancel_order`,
`on_order_cancel_rejected`) and `python/nautilus_trader/model/__init__.pyi`
(`OrderCancelRejected`). Cancel rejection is non-terminal; missing acknowledgement
does not release an order. T22 keeps that identity, freezes and escalates rather
than submitting a replacement under uncertainty. Acknowledgement grace uses the
same bounded per-role timeout, measured from the cancel request.

Durable safety reuses the existing `safety.Ledger.freeze` and follows
`native_adapter.record_callback_fault`: attempt both the durable halt and
fault_sink even if either fails, retain only safe error types, and stop submits.
Tests close/reopen the actual SQLite ledger and separately verify a pre-existing
halt with no exposure. Held stale/halted/closed/budget hazards have durable
handoff, with no automatic resume. The review's native_strategy line reference
differs in this branch; the equivalent verified failure-isolation pattern is in
native_adapter.py:136-164. No shared paper file is modified here.

Clock primary sources at the same rc5 pin are `crates/common/src/python/clock.rs`
and `python/nautilus_trader/common/__init__.pyi` (`Clock.timestamp_ns`). Upstream
does not expose a live-clock constructor or permit setting live time. An actual
installed-client probe verified that a strategy registered through
`LiveNode.add_strategy` receives the native Clock before the run. Fixtures borrow
that clock through an independent no-trade actor, use the actual family actor's
clock for events/quotes/journal timestamps, and declare synthetic RTH at the
calendar boundary. They do not change the engine clock or skip weekends.

Ten new lifecycle regressions include nine that fail against unchanged93871505
(13 assertion failures including subtests). The consumed-entry isolating test
already passes there: no unresolved order, position, halt or exhausted sequence
can explain its refusal, and a new instance enters in the positive control.
Removing only the consumed assignment in the isolated baseline makes that test
fail (sequence3 instead of1); the baseline source is then restored. This is
disclosed as missing coverage, not falsely labelled a repaired behaviour bug.
The corrected native suite passes34 tests with zero skips. Local results remain
synthetic engineering; historical timing, paper and performance gates stand.

## Codex correction at 45ebe5c4

The three reviewed findings reproduce on the immutable
`45ebe5c4e996a53fa0627bbfd2087c1e936e86b0` baseline with only the new regression
module overlaid. The native rc5 focused run fails on policy-cutoff entries and
resting buys, halt cancellation, and callback-clock entry anchoring. Positive
controls admit entries before the cutoff and keep pending exits separate.

Comment 4235547318 now uses the existing `_holding_deadline` calendar resolver
to refuse new entries at the selected policy boundary, and latches that boundary
when submitting an entry so a rollover cannot move a resting buy's deadline.
Comment 4235547324 cancels a pending entry on a halt independently of the pending
exit gate; the identity survives until a native terminal event, and a missing
acknowledgement still freezes with that same identity. Comment 4235547328 anchors
the first buy to `OrderFilled.ts_event`; both its holding timer and selected
calendar deadline therefore describe the fill, including delayed delivery.

The primary API remains
`nautechsystems/nautilus_trader@1b0a49d2792a9432a3aca3fcb617ce7a630d905e`,
`python/nautilus_trader/model/__init__.pyi` (`OrderFilled.ts_event`,
`OrderCanceled`, `OrderCancelRejected`),
`crates/trading/src/python/strategy.rs` (native event dispatch and
`py_cancel_order`) and `crates/common/src/python/clock.rs` (`Clock.timestamp_ns`).
The unchanged installed 2.0.0rc5 engine reproduces the failures and exercises the
fixes through its quote, custom-data, order and timer boundaries. Shared
`adaptive-paper/sessions.py`, backed by
`exchange_calendars@dbe38b1f6887434bbdd1a7d2df6ff8f1742a048a`, still owns calendar
semantics; no replacement calendar or broker adapter is introduced.

The acceptance generator retains its credential-free subprocess environment
without inherited one-thread test caps, following the CC's corrected suite
resource rule. README records lido's exact-head source answer: the T22 local
residual flag has no established bridge to continuing shared-runner management.
That test-backed follow-up remains a T13-runtime gate under the CC ruling;
synthetic landing and paper acceptance are separate.

The final focused baseline run has six tests and nine assertion failures; the
pending-exit separation control already passes. All six pass after the fix. The
regenerated full native receipt has 40 tests, zero skips and 14 matching source
bindings. The matrix has 120 timing candidates, 30 legacy cases, four controls,
ten noncohort inverses and seven matching bindings. Both retain `NOT_CITED`.
