# Chronological daily control evaluation

This native skfolio experiment evaluates causal **raw-price labels** on bundled
LEAN SPY, QQQ and IWM data. It exercises rule selection, chronological boundaries,
complete trial recording and a reserved evaluation segment. It does not simulate
orders, cash, dividends, financing or attainable investment returns.

The [frozen plan](plan.json) fixes momentum lookbacks of 20, 60 and 120 sessions,
cash and equal-weight controls, and a five-session horizon. Each momentum rule
selects the strongest positive trailing raw-close return, otherwise cash. Its
decision at completed close `t` uses a next-open entry label at `t+1` and an exit
open at `t+6`. Episodes occur every five sessions on a fixed global calendar, so
one episode's exit and its successor's entry share an open boundary. These are
nominal data times, not proven original availability times or executable fills.

Data from 2014 provides warm-up. Eligible development begins January 2015 and
ends December 2020. Native `skfolio.model_selection.WalkForward` supplies
252-session training, 63-session evaluation and a six-session exclusion. Asset
rows stay grouped by session. Exact training label ends must also precede the
next evaluation decision. There is no future-side training and no additional
post-evaluation embargo; this does not establish statistical independence.
Evaluation labels can extend across a 63-session fold boundary, but are censored
at the end of their development or reserved segment. Their later outcomes never
enter an earlier selection.

Each fold selects the highest mean training label after its cost proxy among
three momentum rules and cash; ties follow the plan's fixed candidate order.
Equal-weight is a comparison control. All five candidates remain in the ledger,
including unselected, cash and censored outcomes. Every selection is written
exclusively to a new hash-bound record before evaluation labels are materialized.

January–March 2021 is reserved for this particular experiment, not demonstrated
globally unseen history. Its selector uses the last 252 development sessions
before a six-session exclusion. Once scored, these results are inspected evidence
for future work and cannot be presented as a fresh untouched holdout. The last
incomplete horizons remain censored rather than inferred. There is no tuning,
promotion or statistical alpha claim based on the reserved results.

## Observed native results — September 19, 2026

The first and only scoring run completed with exit **0**, empty stderr,
**20 development folds**, **21 frozen selections** including the reserved
selection, and **6,605 candidate records**. All nine source files remained
unchanged. The boundary audit found every observed label's decision before entry
before exit, and every training exit before its evaluation cutoff.

The reserved selector chose **momentum20 from training scores**, before seeing
2021 outcomes. Each candidate has **11 completed five-session episodes and one
censored episode**. The means below are arithmetic price-label summaries,
including the fixed cost proxy; they are not portfolio returns.

| Frozen rule/control | Invested completed episodes | Mean five-session raw-price label | Mean after cost proxy |
| --- | ---: | ---: | ---: |
| momentum20 — selected from training | 10 | 0.300225% | 0.118407% |
| momentum60 | 11 | 0.640313% | 0.440313% |
| momentum120 | 11 | 0.640313% | 0.440313% |
| cash | 0 | 0% | 0% |
| equal-weight control | 11 | 0.362293% | 0.162293% |

The selected rule's reserved mean was below the equal-weight control. The better
unselected outcomes remain visible and do not change the frozen selection.
Eleven completed episodes are insufficient for a claim of persistent advantage.
The [receipt](receipt.json) retains exact decimals, every development fold's
candidate summaries, native commands and private-artifact hashes.

Verification: **12 focused boundary tests passed**; the adopted SDK's complete
repository suite passed **214 tests, zero skips**. The separate environment
contains **19 locked distributions**, including skfolio 1.2.9 and pandas 3.0.6;
the native dependency consistency check passed.

skfolio 1.2.9 is BSD-3-Clause. Its wheel was released September 19, 2026 and is
hash-pinned as `a3faab8f2d77d6663e2b541f04da7a0ee855fcb909966a3bd297b13b21c2c053`.
The installed WalkForward source matches the reviewed immutable source hash in
the receipt. This accepts the splitter used here, not every skfolio optimizer.
Independent review verified all 42 retained artifact hashes, exact public/native
result equality, all 21 selection hashes, the pre-scoring plan/source/lock freeze,
the complete ledger counts and 12 focused tests without rerunning scoring.

## Overfitting controls — September 24, 2026

The [overfitting-controls lane](../overfitting-controls/README.md) computed two
diagnostics offline from this run's retained 6,605-record ledger over 301
development episodes. For the four selection candidates, the deflated Sharpe
ratio is **0.552** and the CSCV probability of backtest overfitting is
**0.776**. The diagnostics add no skill evidence and change no selection. The
reserved segment was not re-scored.

## Native adoption and execution

Keep the working SDK unchanged. Choose a fresh private `WAVE_DIR`, an installed
Python 3.12 or newer, and the existing accepted `LEAN_SOURCE` checkout. The
checked-in hash lock targets the verified Linux/WSL Python environment; another
platform still needs native acceptance.

This study only reads bundled data. If the pinned upstream checkout is absent,
the existing [LEAN source recipe](../engine/README.md) supplies it; a .NET build
is unnecessary for this particular recipe. Do not replace the existing remediated
engine checkout to acquire another copy of its unchanged sample files.

```sh
uv venv --python "$PYTHON" "$WAVE_DIR/venv"
uv pip sync --python "$WAVE_DIR/venv/bin/python" --require-hashes \
  blueprints/us-equities/research-evaluation/requirements.lock
"$WAVE_DIR/venv/bin/python" blueprints/us-equities/research-evaluation/evaluate.py \
  --lean-source "$LEAN_SOURCE" --out "$WAVE_DIR/run-1"
python3 -m unittest discover -s tests -p test_research_evaluation.py -v
```

The runner rejects an existing output directory. It verifies nine pinned
daily/map/factor inputs and writes its plan/source/lock/input freeze **before
parsing or scoring price values**. Raw generated selections, candidate labels,
results and streams belong outside Git. The public receipt preserves compact
outcomes and hashes. A reproduction replays inspected evidence; it does not reset
the reserved segment's status.

To deliberately regenerate dependencies, inspect the selected releases first:

```sh
uv pip compile blueprints/us-equities/research-evaluation/requirements.in \
  --python "$PYTHON" --generate-hashes --no-header \
  --output-file blueprints/us-equities/research-evaluation/requirements.lock
```

## Price and evidence boundaries

The three ETFs are a curated control universe, not all historically eligible
equities. The runner requires aligned calendars and the pinned sample's annual
row counts; it checks positive finite OHLC and rejects changing split factors or
symbol mappings in the studied interval. LEAN's factor and map rows apply up to
their row date. All inputs, including factor/map files, are hash-verified.

Raw prices retain ex-dividend declines. Distribution-related price factors are
observed but not applied, and cash distributions are not added. The reported
labels therefore exclude total-return accounting. A fully invested episode is
charged a fixed illustrative 20-basis-point round-trip deduction, independent of
shares, turnover netting, spreads and liquidity; cash has zero cost and
equal-weight receives the same aggregate deduction as a single-asset rule.
Means of these labels are **not portfolio P&L**, annualized returns or Sharpe.
Financing and borrowing are absent. No live feeds, model call or broker order is
needed. Native LEAN execution and cash reconciliation remain separate earlier
acceptances; this recipe makes no new engine-execution claim.

## Primary sources

- [skfolio WalkForward](https://skfolio.org/generated/skfolio.model_selection.WalkForward.html): native chronology, row-gap and delayed-execution semantics.
- [Reviewed skfolio source](https://github.com/skfolio/skfolio/blob/c99fcf71349e2df4a7a1033ee85ca2e9ced9abee/src/skfolio/model_selection/_walk_forward.py): the row gap is not an event-interval purge engine.
- [skfolio 1.2.9 package metadata](https://pypi.org/pypi/skfolio/1.2.9/json): exact upstream distribution and dependencies.
- [LEAN map lookup](https://github.com/QuantConnect/Lean/blob/985ef30ad3ac774218c5ac516b4cb0aa2655730f/Common/Data/Auxiliary/MapFile.cs): first row with date at or after the requested session.
- [LEAN corporate factor provider](https://github.com/QuantConnect/Lean/blob/985ef30ad3ac774218c5ac516b4cb0aa2655730f/Common/Data/Auxiliary/CorporateFactorProvider.cs): factor lookup and split semantics.
