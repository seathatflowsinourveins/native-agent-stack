# Optional overfitting parity against RiskLabAI 3.2.0

Date: 2026-10-05. Lane: trading. Base: `f946c6d4ca988a17b6fa4392ecb488909f147883`.
North-star action: preserve the meaning of US-equities historical-research
selection diagnostics before independently qualified broker paper operation.

Preserve the standard-library-only frozen `overfitting.py` in this bounded
comparison and call the published RiskLabAI wheel directly from the tests.
Five policy differences remain; item 2 is only a difference of the list-based
benchmark API. RiskLabAI already supplies independently specified trial count
and dispersion through `expected_max_sharpe_ratio`, and DSR through
`deflated_sharpe_gate`. The repaired tests use those native functions. No control
or frozen protocol changes, gate promotion, market-data run or convergence
claim follow from this check.

## Sources and verification

The source is [RiskLabAI/RiskLabAI.py at
`7d5aa11271c70d83a7069d5900d80bb08b29e481`](https://github.com/RiskLabAI/RiskLabAI.py/tree/7d5aa11271c70d83a7069d5900d80bb08b29e481).
Its [packaging](https://github.com/RiskLabAI/RiskLabAI.py/blob/7d5aa11271c70d83a7069d5900d80bb08b29e481/pyproject.toml#L6-L12)
declares version 3.2.0 and Python `>=3.12,<3.15`. Its
[installation recipe](https://github.com/RiskLabAI/RiskLabAI.py/blob/7d5aa11271c70d83a7069d5900d80bb08b29e481/README.md#L55-L76)
supports a PyPI base install and the `test` extra. The pinned
[changelog](https://github.com/RiskLabAI/RiskLabAI.py/blob/7d5aa11271c70d83a7069d5900d80bb08b29e481/CHANGELOG.md#L6-L34)
still labels 3.2.0 unreleased; publication was verified separately from PyPI's
version-specific metadata and the installed distribution. All five exercised
installed source files are byte-identical to the commit's packaged `src/`
files, as recorded in the [receipt](../../blueprints/us-equities/overfitting-controls/riskl-parity-receipt.json).
Round 1 inspected four function signatures and missed the separate trial-count
API. Round 2 verifies the additional installed signatures and the pinned
[expected maximum Sharpe implementation](https://github.com/RiskLabAI/RiskLabAI.py/blob/7d5aa11271c70d83a7069d5900d80bb08b29e481/src/RiskLabAI/backtest/test_set_overfitting.py#L12-L56)
and [native DSR gate](https://github.com/RiskLabAI/RiskLabAI.py/blob/7d5aa11271c70d83a7069d5900d80bb08b29e481/src/RiskLabAI/backtest/validation/leakage_aware_hpo.py#L177-L240).
Both import under the existing lock without installing Optuna.

The selected `search-first` and `modern-python` skills informed the source and
environment review. This bounded job follows the repository's existing hashed
requirements recipe rather than migrating its packaging. Research tooling uses
the `research-runtime` profile in [adoption/manifest.json](../../adoption/manifest.json),
whose [research-evaluation recipe](../../blueprints/us-equities/research-evaluation/README.md#native-adoption-and-execution)
creates an isolated `WAVE_DIR/venv` from `requirements.in` and a hash-pinned
`requirements.lock` using `uv pip compile` and `uv pip sync --require-hashes`.
The parity inputs and lock live beside the controls and do not change that
study's dependency set. Verification used installed uv 0.12.17 and CPython
3.12.3 on Linux x86_64; this is the accepted runtime scope.
The research lock is inventoried in
[.github/osv-scanner-lockfiles.json](../../.github/osv-scanner-lockfiles.json)
and participates in the required [OSV scan](../../.github/workflows/security-scan.yml).
The trading-lane owner maintains these pins: bump and re-qualify affected
packages when an advisory arrives, or record a reasoned, time-limited ignore
under the repository's OSV policy. Optional parity execution does not exempt
the lock from that required check.

## Five policy differences and one list-API difference

Local line references below are in the unchanged
[`overfitting.py`](../../blueprints/us-equities/overfitting-controls/overfitting.py).
Each numbered difference has its own test.

| # | Pinned upstream behavior | Repository behavior and reason |
| --- | --- | --- |
| 1 | [PSR lines 78–86](https://github.com/RiskLabAI/RiskLabAI.py/blob/7d5aa11271c70d83a7069d5900d80bb08b29e481/src/RiskLabAI/backtest/probabilistic_sharpe_ratio.py#L78-L86): a non-positive variance denominator returns `0.0` in probability mode. | Lines 65–67 raise `ValueError`. Invalid moment combinations remain input errors instead of becoming an apparently valid probability. Tests cover zero and negative denominators. |
| 2 | Only the [list-based benchmark API](https://github.com/RiskLabAI/RiskLabAI.py/blob/7d5aa11271c70d83a7069d5900d80bb08b29e481/src/RiskLabAI/backtest/probabilistic_sharpe_ratio.py#L99-L144) infers trial count and returns the sole estimate. The separately exported [expected-max function](https://github.com/RiskLabAI/RiskLabAI.py/blob/7d5aa11271c70d83a7069d5900d80bb08b29e481/src/RiskLabAI/backtest/test_set_overfitting.py#L12-L56) already takes independent N, mean and dispersion. | Lines 72–81 match the native function with mean `0.0` and std `sqrt(variance)`, including N=1. The local API requires a positive integer count. This is not an upstream capability gap; these functions remain unchanged solely to preserve this PR's frozen stdlib controls. |
| 3 | [PBO line 129](https://github.com/RiskLabAI/RiskLabAI.py/blob/7d5aa11271c70d83a7069d5900d80bb08b29e481/src/RiskLabAI/backtest/probability_of_backtest_overfitting.py#L128-L130): `np.array_split` keeps all rows and permits unequal blocks. | Lines 159–167 drop the earliest remainder so complementary halves have equal observation counts. The fixture's early outlier makes upstream PBO `1.0` and local PBO `0.0`; removing it restores parity. |
| 4 | [PBO lines 69–73](https://github.com/RiskLabAI/RiskLabAI.py/blob/7d5aa11271c70d83a7069d5900d80bb08b29e481/src/RiskLabAI/backtest/probability_of_backtest_overfitting.py#L69-L73): double `argsort` gives ordinal tied ranks with unspecified tie order. | Lines 116–127 and 181 average tied out-of-sample ranks, avoiding an arbitrary distinct rank for equal performance. Both implementations pick the first in-sample maximum. The fixture's selected rank is upstream `2` or `3` by tie order, local `2.5`; the test accepts both valid ordinal results. |
| 5 | [PBO lines 77 and 153–156](https://github.com/RiskLabAI/RiskLabAI.py/blob/7d5aa11271c70d83a7069d5900d80bb08b29e481/src/RiskLabAI/backtest/probability_of_backtest_overfitting.py#L77-L156): returns non-strict PBO (`lambda <= 0`) and logits. | Lines 188–197 expose both `pbo` and `pbo_strict` (`lambda < 0`) and count zero logits, making exact-median cases visible. A fixture without tied metric values gives non-strict `1.0`, strict `0.0`. Upstream logits permit a caller to derive strict PBO, but it is not a separately returned statistic. |
| 6 | [Sharpe lines 50–56](https://github.com/RiskLabAI/RiskLabAI.py/blob/7d5aa11271c70d83a7069d5900d80bb08b29e481/src/RiskLabAI/backtest/backtest_statistics.py#L50-L56): exactly zero standard deviation returns `0.0`; a positive near-zero standard deviation gives a finite, possibly huge ratio. | Lines 48–53 raise for zero variance **with nonzero mean**. In CSCV, lines 104–112 also treat `std <= 1e-12 * max(1, abs(mean))` as zero after merging. Standalone Sharpe, a constant nonzero CSCV column, and a near-constant column below this threshold are tested; upstream produces finite PBO while local CSCV raises. Constant zero returns agree. |

Correction to job-073's overfitting adjudication (lines 46 and 69): the claim
that RiskLabAI lacks independently specified trial count and dispersion is
false at the cited pin. `test_set_overfitting.py:12–56` supplies that function,
and `validation/leakage_aware_hpo.py:177–240` supplies DSR. The repaired suite
executes both; all five installed module hashes match a fresh pinned upstream
fetch. This corrects the round-1 decision and receipt. The original private
adjudication is outside this worktree's writable scope; its owner must carry
this correction to those two lines.

Difference 6 is narrower than an unconditional standalone local exception,
and includes a CSCV near-zero threshold. Difference 2 does not mean the local
API accepts fractional effective counts; its count must be a positive integer.
The upstream PBO locator is
`src/RiskLabAI/backtest/probability_of_backtest_overfitting.py`, rather than a
file named `pbo.py`. The source lines above and installed executions establish
these qualifications.

## Comparison and adoption trigger

Regular fixtures compare PSR, both benchmark APIs, the native DSR gate,
population-standard-deviation Sharpe, and every CSCV logit for both mean and
Sharpe metrics at four and eight equal partitions. Supplied-N benchmark cases
cover N in `{1, 2, 5, 100}` and variance in `{0, 0.01, 1}`; native DSR uses
fixed four- and six-return series. Absolute tolerance is `1e-12`; relative
tolerance is `1e-11` for the supplied-N benchmark and native DSR, `1e-12`
otherwise. Upstream rounds Euler's constant to `0.5772156649` at
`test_set_overfitting.py:49`; the observed N=2, variance=1 relative gap is
about `2.66e-12`. This is numerical rounding, not a missing trial-count feature.
CSCV regular cases have nonconstant columns, no ranking ties and PBO strictly
between zero and one.

Four regression checks failed against the original comparison behavior before
repair: supplied-N numeric tolerance, native DSR oracle sensitivity, alternate
ordinal tie order, and CSCV degenerate-Sharpe oracle sensitivity. Fourteen
repaired tests pass with RiskLabAI present and all fourteen skip in an empty
venv. Twelve unchanged selected upstream tests pass separately. Seven scratch
mutations of the local controls (one per numbered case and one for policy 6's
threshold) fail under native unittest. The receipt preserves the red and green
results, the intermediate failed repair, source hashes and the historical
round-1 observations.

Completeness critic: this review covers the chosen PSR/benchmark/PBO APIs and
the supplied-N benchmark, native DSR gate and PBO Sharpe function, including
both supported local metrics, singleton trials, zero-variance estimates,
CSCV constant and near-constant columns, denominator boundaries, uneven row
counts, both ordinal tie orders and exact-median logits. Default and disabled
x86_64 CPU-feature runs passed. An arm64 host was unavailable, so that host's
execution remains unverified. It excludes other upstream Sharpe functions,
optional Numba acceleration, unrelated cross-validation methods and market
qualification. Those exclusions do not establish whole-library equivalence.

Thin caller-side glue can retain policy 1 through a variance pre-check before
[PSR](https://github.com/RiskLabAI/RiskLabAI.py/blob/7d5aa11271c70d83a7069d5900d80bb08b29e481/src/RiskLabAI/backtest/probabilistic_sharpe_ratio.py#L78-L96),
policy 3 by trimming the earliest remainder before the
[partition step](https://github.com/RiskLabAI/RiskLabAI.py/blob/7d5aa11271c70d83a7069d5900d80bb08b29e481/src/RiskLabAI/backtest/probability_of_backtest_overfitting.py#L128-L130),
policy 5 by counting `< 0` in the
[returned logits](https://github.com/RiskLabAI/RiskLabAI.py/blob/7d5aa11271c70d83a7069d5900d80bb08b29e481/src/RiskLabAI/backtest/probability_of_backtest_overfitting.py#L151-L156),
and policy 6 with the supported
[metric callback](https://github.com/RiskLabAI/RiskLabAI.py/blob/7d5aa11271c70d83a7069d5900d80bb08b29e481/src/RiskLabAI/backtest/probability_of_backtest_overfitting.py#L80-L85).
These require no upstream feature additions. The actual CSCV gaps are the
hard-coded ordinal rank in `performance_evaluation:69–73` and the additional
required selection, loss and degradation diagnostics returned locally at
`overfitting.py:194–205`.

Reopen direct CSCV adoption when upstream supports an average-rank option.
Require the additional diagnostics either from upstream or from a documented
thin adapter that avoids rebuilding upstream CSCV. Re-pin and qualify that
adapter against the retained policies. Expected-max Sharpe and DSR already
have native implementations and should use them in a separately scoped
runtime-adoption change; preserving this PR's frozen stdlib controls is the
only reason they remain here. Popularity or regular-case parity alone does not
overturn the remaining CSCV gaps.

## Reproduce without touching the working research environment

Choose an already installed Python 3.12–3.14 as `PYTHON`. Installs and caches
stay under the requested private scratch root. Commands run with niceness 19.
The unittest module itself performs no network access or package installation.
Absent or mismatched RiskLabAI versions skip; an import failure is an explicit
skip reason. Inspect the test count and skip count when qualifying a present
install; an optional skip is not execution evidence.

```sh
export TMPDIR="$HOME/.cache/tparity2"
export UV_CACHE_DIR="$TMPDIR/uv-cache"
rtk nice -n 19 mkdir -p "$TMPDIR"
PARITY_DIR=$(rtk nice -n 19 mktemp -d "$TMPDIR/overfitting-riskl-parity.XXXXXX")
rtk nice -n 19 uv venv --python "$PYTHON" --no-python-downloads "$PARITY_DIR/venv"
rtk nice -n 19 uv pip sync --python "$PARITY_DIR/venv/bin/python" \
  --no-python-downloads --require-hashes --only-binary :all: \
  blueprints/us-equities/overfitting-controls/requirements-riskl-parity.lock
rtk nice -n 19 "$PARITY_DIR/venv/bin/python" -m unittest tests.test_overfitting_riskl_parity -v
rtk nice -n 19 uv venv --python "$PYTHON" --no-python-downloads --offline \
  "$PARITY_DIR/without-riskl"
rtk nice -n 19 "$PARITY_DIR/without-riskl/bin/python" -m unittest tests.test_overfitting_riskl_parity -v
rtk nice -n 19 python3 -m unittest tests.test_overfitting_controls -v
```

The checked-in lock pins all 19 packages and their distribution hashes. It was
generated through the same supported command as the research-evaluation recipe:

```sh
rtk nice -n 19 uv pip compile \
  blueprints/us-equities/overfitting-controls/requirements-riskl-parity.in \
  --python "$PYTHON" --no-python-downloads --generate-hashes --no-header \
  --output-file blueprints/us-equities/overfitting-controls/requirements-riskl-parity.lock
```
