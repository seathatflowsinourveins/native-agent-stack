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

`python3 -m unittest tests.test_extreme_gainer_audit`: 15 tests with made-up tickers, dates and prices; no network, credentials or package rows.

## Run 2026-09-24 (`run-20260924a`, fetch code `4cb31878`)

- **Fetch:** 2,871 requests, all HTTP 200, at 02:52:04Z. The plan was committed and published at 02:51:57Z.
  `plan.json`'s `frozen_at_utc` field is wrong (deviation D5). The snapshot (sha256 `0d98909f…`) and the per-event
  results stay private; their sha256 values are in the committed summaries.
- **Symbols:** each event was queried under one symbol, with `asof` set to its date. The alias fallback never ran,
  because none of the 5 no-data events had an alias entry. A supplement fetch (deviation D3) later recovered OCTO
  under its original ticker.
- **Determinism:** `compare` and `posthoc.py` reruns are byte-identical under both rule sets.

### Preregistered result (`--rules v1`): the overturn triggered, and this result stands

| Verdict | Rows |
|---|---|
| match / mismatch (both priced) | 535 / 137, which is 20.4% of 672 and above the 5% threshold |
| recovered_match / recovered_mismatch | 215 / 59 (of these 274, 7 are Status OK rows without a computed gain; see D4) |
| no_prev_close / no_source_data | 6 / 5 |

### Corrected implementation (`--rules v2`, same snapshot plus the D3 supplement; `deviations.json`)

Independent review found an implementation defect: with several condition-6 closing prints on a day, v1 took the
first print from any exchange, not the listing exchange's (D1). The review also found three smaller issues: the
split tolerance fired on adjustment rounding (D2), the original `Ticker` was never tried (D3), and seven rows were
misnamed "recovered" (D4). Under v2:

| Verdict | Rows |
|---|---|
| match / mismatch | 589 / 84, which is 12.5% of 673. The overturn still triggers. |
| recovered_match / recovered_mismatch | 222 / 45 (16.9% of 267) |
| package_uncomputed_match / _mismatch | 6 / 1 |
| no_prev_close / no_source_data | 6 / 4 |
| split between the two closes | 3 (ELTX, QXO and UZX; v1 flagged 57, of which 54 were rounding) |

Forward returns (split-adjusted) agree under both rule sets: T+1 659/673, T+5 653/662 and T+20 631/646 under v2.

### Post-hoc decomposition (`posthoc.py`; not preregistered, so it explains the verdicts without changing them)

Under v2, among the 643 rows the package priced itself and did not flag:
- 567 (88.2%) agree with the official-close gain, and 627 (97.5%) agree with a gain from Alpaca's daily-bar closes.
- 60 rows agree only on the bar basis, and 16 disagree on both.
- The daily-bar close differs from the official close by more than 0.5% on 4.5% of event and previous days, with a
  p95 of 0.29%. Under v1 the same figure read 8.5%, which was inflated by D1.

What this does and does not establish:
- The package's prices are consistent with a last-trade daily close more often than with the official close. That
  its closes include after-hours prints is an inference: no intraday data here isolates the prints.
- The bar basis comes from the same provider as the official closes, so agreement on it is not third-source
  verification.
- The package's own flagged rows include four reused tickers (LOGC, TEN, BTX, CBIO). There, `asof` returns the
  company that traded on the event date.

### Still owed under the overturn rule

Each preregistered mismatch must be adjudicated against a third source before the package's price-derived statistics
are used: 137 under v1, and 84 plus 45 recovered mismatches under v2. Until then those statistics are unverified.
