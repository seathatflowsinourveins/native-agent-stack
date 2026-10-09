# T22 sources and corrections, 2026-10-09

The ten §6 families and three preset columns are untested hypotheses beside the
frozen #16 study. The scope record is us-equities-trading #25 at
`7dfa652ac36195ea1e0b3df77f915e35fd3d4c81`, read through `git show` after fetching
the PR head. No rank rows, labels or study arms are inputs to these classes.

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
