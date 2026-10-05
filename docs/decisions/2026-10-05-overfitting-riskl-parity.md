# Optional overfitting parity against RiskLabAI 3.2.0

Date: 2026-10-05. Lane: trading. Base: `f946c6d4ca988a17b6fa4392ecb488909f147883`.
North-star action: preserve the meaning of US-equities historical-research
selection diagnostics before independently qualified broker paper operation.

Keep `overfitting.py` as policy glue and add an optional synthetic comparison
with the published RiskLabAI wheel. Direct replacement would change the six
semantics below. Rebuilding or vendoring RiskLabAI is unnecessary: call its
installed functions, using its supported metric callback for the local mean
metric and its benchmark Sharpe plus PSR for DSR. No control or frozen protocol
changes, gate promotion, market-data run or convergence claim follow from this
check.

## Sources and verification

The source is [RiskLabAI/RiskLabAI.py at
`7d5aa11271c70d83a7069d5900d80bb08b29e481`](https://github.com/RiskLabAI/RiskLabAI.py/tree/7d5aa11271c70d83a7069d5900d80bb08b29e481).
Its [packaging](https://github.com/RiskLabAI/RiskLabAI.py/blob/7d5aa11271c70d83a7069d5900d80bb08b29e481/pyproject.toml#L6-L12)
declares version 3.2.0 and Python `>=3.12,<3.15`. Its
[installation recipe](https://github.com/RiskLabAI/RiskLabAI.py/blob/7d5aa11271c70d83a7069d5900d80bb08b29e481/README.md#L55-L76)
supports a PyPI base install and the `test` extra. The pinned
[changelog](https://github.com/RiskLabAI/RiskLabAI.py/blob/7d5aa11271c70d83a7069d5900d80bb08b29e481/CHANGELOG.md#L6-L34)
still labels 3.2.0 unreleased; publication was verified separately from PyPI's
version-specific metadata and the installed distribution. All three exercised
installed source files are byte-identical to the commit's packaged `src/`
files, as recorded in the [receipt](../../blueprints/us-equities/overfitting-controls/riskl-parity-receipt.json).
Installed function signatures were inspected before making API claims.

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

## Six confirmed differences and retained policies

Local line references below are in the unchanged
[`overfitting.py`](../../blueprints/us-equities/overfitting-controls/overfitting.py).
Each numbered difference has its own test.

| # | Pinned upstream behavior | Repository behavior and reason |
| --- | --- | --- |
| 1 | [PSR lines 78–86](https://github.com/RiskLabAI/RiskLabAI.py/blob/7d5aa11271c70d83a7069d5900d80bb08b29e481/src/RiskLabAI/backtest/probabilistic_sharpe_ratio.py#L78-L86): a non-positive variance denominator returns `0.0` in probability mode. | Lines 65–67 raise `ValueError`. Invalid moment combinations remain input errors instead of becoming an apparently valid probability. Tests cover zero and negative denominators. |
| 2 | [Benchmark lines 99, 133–144](https://github.com/RiskLabAI/RiskLabAI.py/blob/7d5aa11271c70d83a7069d5900d80bb08b29e481/src/RiskLabAI/backtest/probabilistic_sharpe_ratio.py#L99-L144): trial count is the estimate-list length; one estimate returns that estimate. | Lines 72–81 accept a separately supplied positive integer trial count and cross-trial variance; one trial has null benchmark `0.0`. This preserves externally justified effective counts and the no-selection null. The retained study still uses its frozen raw candidate count. |
| 3 | [PBO line 129](https://github.com/RiskLabAI/RiskLabAI.py/blob/7d5aa11271c70d83a7069d5900d80bb08b29e481/src/RiskLabAI/backtest/probability_of_backtest_overfitting.py#L128-L130): `np.array_split` keeps all rows and permits unequal blocks. | Lines 159–167 drop the earliest remainder so complementary halves have equal observation counts. The fixture's early outlier makes upstream PBO `1.0` and local PBO `0.0`; removing it restores parity. |
| 4 | [PBO lines 69–73](https://github.com/RiskLabAI/RiskLabAI.py/blob/7d5aa11271c70d83a7069d5900d80bb08b29e481/src/RiskLabAI/backtest/probability_of_backtest_overfitting.py#L69-L73): double `argsort` gives ordinal tied ranks. | Lines 116–127 and 181 average tied out-of-sample ranks, avoiding an arbitrary distinct rank for equal performance. Both implementations pick the first in-sample maximum. The fixture's selected rank is upstream `2`, local `2.5`. |
| 5 | [PBO lines 77 and 153–156](https://github.com/RiskLabAI/RiskLabAI.py/blob/7d5aa11271c70d83a7069d5900d80bb08b29e481/src/RiskLabAI/backtest/probability_of_backtest_overfitting.py#L77-L156): returns non-strict PBO (`lambda <= 0`) and logits. | Lines 188–197 expose both `pbo` and `pbo_strict` (`lambda < 0`) and count zero logits, making exact-median cases visible. A fixture without tied metric values gives non-strict `1.0`, strict `0.0`. Upstream logits permit a caller to derive strict PBO, but it is not a separately returned statistic. |
| 6 | [Sharpe lines 50–56](https://github.com/RiskLabAI/RiskLabAI.py/blob/7d5aa11271c70d83a7069d5900d80bb08b29e481/src/RiskLabAI/backtest/backtest_statistics.py#L50-L56): zero standard deviation returns `0.0`. | Lines 48–53 raise for zero variance **with nonzero mean**, preventing a degenerate nonzero return series from being scored as zero skill. Constant zero returns give `0.0` on both sides and are also tested. |

Verification correction: difference 6 is narrower than an unconditional local
exception. Difference 2 does not mean the local API accepts fractional effective
counts; its count must be a positive integer. The upstream PBO locator is
`src/RiskLabAI/backtest/probability_of_backtest_overfitting.py`, rather than a
file named `pbo.py`. The source lines above and installed executions establish
these qualifications.

## Comparison and adoption trigger

Regular fixtures compare PSR, population-variance benchmark Sharpe, composed
DSR, population-standard-deviation Sharpe, and every CSCV logit for both mean
and Sharpe metrics at four and eight equal partitions. Absolute and relative
tolerances are both `1e-12`. CSCV cases have nonconstant columns, no ranking
ties and PBO strictly between zero and one. Ten local tests pass with RiskLabAI
present and all ten skip in a fresh empty venv. Eight unchanged upstream tests
pass separately; they are not the locally authored parity tests. A scratch copy
with difference 3's expected upstream PBO changed to `0.5` fails with exit 1,
demonstrating that the divergence assertion is active. Actual returned results,
source hashes and the failed control are retained in the receipt.

Completeness critic: this review covers the chosen PSR/benchmark/PBO APIs and
the PBO Sharpe function, including both supported local metrics, singleton
trials, zero-variance estimates, denominator boundaries, uneven row counts,
tied ranks and exact-median logits. It excludes other upstream Sharpe functions,
optional Numba acceleration, unrelated cross-validation methods and market
qualification. Those exclusions do not establish whole-library equivalence.

Reopen direct adoption when a released upstream API can take independently
specified trial count and variance, report strict PBO, and select the retained
denominator, degenerate-Sharpe, equal-block and average-rank policies. Re-pin
the clean install and deliberately review the changed divergence expectations;
adopt only after regular parity and all six policy fixtures agree with those
options. Popularity or regular-case formula parity alone does not overturn this
decision. The alternative of retaining only hand-derived crosschecks lacks the
independent installed-upstream comparison added here.

## Reproduce without touching the working research environment

Choose an already installed Python 3.12–3.14 as `PYTHON`. Installs and caches
stay under the requested private scratch root. Commands run with niceness 19.
The unittest module itself performs no network access or package installation.
Absent or mismatched RiskLabAI versions skip; an import failure is an explicit
skip reason. Inspect the test count and skip count when qualifying a present
install; an optional skip is not execution evidence.

```sh
export TMPDIR="$HOME/.cache/tparity"
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
