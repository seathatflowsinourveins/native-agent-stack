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
