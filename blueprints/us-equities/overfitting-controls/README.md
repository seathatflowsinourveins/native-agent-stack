# Backtest-overfitting controls

This lane adds two selection-bias diagnostics to the multi-candidate research
lane and applies them to the retained
[research-evaluation](../research-evaluation/README.md) candidate ledger:

- **Deflated Sharpe ratio (DSR)**, Bailey and Lopez de Prado (2014): the
  probabilistic Sharpe ratio of the best trial, measured against the expected
  maximum Sharpe of N null trials rather than zero.
- **Probability of backtest overfitting (PBO)** by combinatorially symmetric
  cross-validation (CSCV), Bailey, Borwein, Lopez de Prado and Zhu (2017): the
  share of in-sample/out-of-sample block splits in which the in-sample best trial
  ranks at or below the out-of-sample median.

[`overfitting.py`](overfitting.py) implements both from the papers using only the
Python standard library. Nothing was copied or vendored. The citations and the
formulas are in its docstring. [`evaluate.py`](evaluate.py) applies the module
offline to the hash-pinned ledger using the parameters in
[`params.json`](params.json). Those parameters were frozen before the first
computation. [`crosscheck.py`](crosscheck.py) recomputes the primary DSR and PBO
independently with numpy.

## Result — September 24, 2026

Input: the 6,605-record candidate ledger (SHA-256 `08ea5309…2f42672`, equal to
the research-evaluation receipt's `ledger_sha256`). The in-tree copy is the
byte-identical gap-wave2 regeneration. No data was refetched. After
deduplication, the development segment has 301 aligned five-session episodes per
candidate, from 2015-01-02 to 2020-12-16. The reserved 2021Q1 segment is
excluded.

| Diagnostic (frozen four-candidate selection set) | Value |
| --- | ---: |
| Best per-episode Sharpe (momentum120), not annualized | 0.0254 |
| Expected maximum null Sharpe SR0 (N = 4) | 0.0177 |
| PSR against zero | 0.667 |
| **Deflated Sharpe ratio** | **0.552** |
| **PBO** (S = 16, mean-label metric, 12,870 splits) | **0.776** |
| Probability that the selected trial loses out of sample | 0.480 |
| Walk-forward selected series: Sharpe / PSR(0), 249 episodes | -0.0151 / 0.405 |

All sensitivity cells give PBO (lambda <= 0) between 0.76 and 0.96. The cells
cover S = 8, 10, 12 and 16, the mean and Sharpe metrics, and three trial sets:
the primary four, adding the equal-weight control, and momentum rules only.
DSR stays between 0.55 and 0.58. The [receipt](receipt.json) retains every cell,
the strict lambda < 0 shares, input and source hashes, commands and the
independent recomputation.

The receipt also keeps the paper's degradation slope (the selected trial's
out-of-sample metric regressed on its in-sample metric; -0.727 in the primary
cell). It is not used as evidence. With the mean metric and equal complementary
halves, each trial's in-sample mean plus its out-of-sample mean equals twice its
mean over all used rows. Every split that selects the same trial therefore lies
on a line of slope exactly -1, and momentum120 is selected in 5,490 of the
12,870 splits. The pooled slope is pulled towards -1 by construction, and it
says almost nothing about whether rankings persist.

**Conclusion.** These retained candidates show no deflated-Sharpe evidence of
skill. The in-sample best candidate usually ranks below the out-of-sample
median. With four trials and no skill, PBO would be about 0.5, so 0.776 is
consistent with selection noise or mild anti-persistence of in-sample ranking,
not skill. The CSCV splits overlap heavily and PBO has no p-value, so this
reading is descriptive. This negative diagnostic covers only this three-ETF
control lane. It does not tune, promote or reject any future strategy.

## Boundaries

- The inputs are raw-price five-session labels less a fixed 20bp proxy, not
  portfolio returns. The Sharpe values are per-episode label ratios.
- N counts only this lane's frozen candidates. The research program ran other
  trials, so relative to all of them this DSR is optimistic. No effective-N
  clustering was applied. momentum60 and momentum120 share about 60% of their
  development labels.
- With three to five correlated trials, CSCV has only a few distinct ranks.
  Contiguous 18-episode blocks are assumed exchangeable. PBO is descriptive and
  has no p-value.
- Evidence class: a local integration check with an independent numpy
  recomputation. The DSR unit test reproduces the paper's numerical example
  (SR0 0.1132, DSR 0.9004). Those constants are transcribed from the paper,
  which was not re-fetched offline. The PBO tests are locally constructed
  synthetic fixtures. No upstream implementation was executed.

## Reproduce

```sh
python3 blueprints/us-equities/overfitting-controls/evaluate.py
python3 -m unittest tests.test_overfitting_controls -v
# optional independent recomputation (needs numpy)
python blueprints/us-equities/overfitting-controls/crosscheck.py
```

Reusing the module for another candidate ledger: pass a T x N matrix of
per-period trial performance to `cscv_pbo`. Pass the selected trial's Sharpe,
moments, trial count and cross-trial Sharpe variance to `deflated_sharpe`.
Freeze the trial set and the parameters before looking at the results. Count
every trial that was actually tried.
