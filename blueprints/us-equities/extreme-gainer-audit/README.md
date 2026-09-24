# Extreme-gainer price audit

An independent re-derivation of the price facts in a third-party research package (the "extreme-gainer
incentive research package"): 957 extreme single-day gainer events, 2021 to September 2026. The package took its
event-day prices from a single source. This audit recomputes every event's gain, and its T+1/T+5/T+20 forward
returns, from Alpaca SIP official closes.

- `plan.json` is the preregistration, frozen before the first run: inputs by SHA-256, source, official-close rule,
  gain and forward-return definitions, tolerances, verdicts and the overturn rule.
- `audit.py fetch` writes the raw API responses to a private snapshot (market data is not redistributed) and
  records its SHA-256.
- `audit.py compare` is deterministic: the same snapshot and package CSVs give byte-identical results.
- The package itself stays in the private research intake. It is identified here only by the SHA-256 values in
  `plan.json`.

## Reproduce

```
python3 audit.py fetch --env-file PAPER_ENV --package-dir PKG --out-dir PRIVATE
python3 audit.py compare --snapshot PRIVATE/snapshot.json --package-dir PKG --out results.json
```

`compare` refuses inputs whose SHA-256 differs from the plan's, and a snapshot fetched under a different plan. A
later `fetch` can differ if the provider revises history. Compare two snapshots through their result tables, not
their bytes.

## Tests

`python3 -m unittest tests.test_extreme_gainer_audit` (synthetic; no network, credentials or package files).

## Run 2026-09-24 (`run-20260924a`, code `4cb31878`)

- **Fetch:** 2,871 requests, all HTTP 200, at 02:52Z. Snapshot sha256 `0d98909f…`, kept private with the per-event
  results (their sha256 values are in `evidence/summary-run-20260924a.json`). With `asof` set to each event date,
  Alpaca resolved every event's original ticker, so no alias fallback was needed.
- **Determinism:** `compare` twice gave byte-identical results; `posthoc.py` twice likewise.

Preregistered results. The overturn threshold was reached, and those verdicts stand.

| Verdict | Rows |
|---|---|
| match (both priced, within tolerance) | 535 |
| mismatch (both priced) | 137, which is 20.4% of 672 and above the 5% overturn threshold |
| recovered_match (package had no prices; Alpaca agrees with its catalogued gain) | 215 |
| recovered_mismatch | 59, which is 21.5% of 274 recovered rows |
| no_prev_close / no_source_data | 6 / 5 |

Forward returns (split-adjusted) agree far more often: T+1 658/672, T+5 652/661, T+20 630/645. 57 rows had a split
between the two closes; 20 rows needed the bar-close fallback.

Post-hoc decomposition (`posthoc.py`; not preregistered, so it explains the verdicts without changing them):
- **Basis difference.** Of the 642 rows the package priced itself and did not flag, 515 (80.2%) agree with the
  official-close gain and 626 (97.5%) agree with a gain from Alpaca's daily-bar closes. So on its own basis the
  package's prices reproduce independently. It measures close-to-close from the day's last trade, which can be an
  after-hours print. The 111 rows that agree only on the bar basis are that definitional difference.
  - Size of the gap between bar close and official close: 8.6% of event and previous days differ by more than
    0.5%, and the p95 is 1.08%. On extreme movers, after-hours prints move the "day's gain".
- **Mismatch classes.**
  - 109: the closes match Alpaca's bar closes but not the official close.
  - 11: a split between the two closes.
  - 10: rows the package itself had flagged (ticker reuse, artifacts, corrections).
  - 7: one or both closes differ outright.
- **Ticker reuse.** The package's flagged rows include four reused tickers, where its source keys history by today's
  ticker. Alpaca's `asof` returns the company that traded on the event date. These rows are candidates to restore
  after a third-source check.
- **Still to adjudicate.** The overturn rule requires a third source for the 16 rows that disagree on both bases and
  the 59 recovered mismatches.
