# Mover early-entry studies (v1 and v2, preregistered)

Can long-only rules that use only information available early in a session (or at the previous close) select
US-equity movers whose returns are positive net of realistic costs, with a preregistered auto-leverage schedule? For
each degree of eventual move, what share of movers do they catch, and how early?

- **v1** `protocol.json` (`mover-early-entry-v1-20260924`, frozen at `4e57667a`): 8 clock times x 4 gain thresholds x
  3 dollar-volume floors x 2 news variants x 4 exits = 768 rule-exits.
- **v2** `protocol-v2.json` (`mover-followup-v2-20260924`, frozen at `a4a2f682` before any v1 or v2 outcome):
  E first-cross (earliest-stage) entries, F opening-range / pre-market-high / VWAP-reclaim setups, P pre-positioning at
  the previous close and day-2 continuation.

Departures are dated in `deviations.json` (D1-D5); readings the text leaves open in `clarifications.json` (C1-C32) and
`clarifications-v2.json` (V1-V14). All were fixed before the outcome they could affect.

## Result so far (v1, development and validation)

`evidence/summary-dev-val-run-v1.json` (aggregates; results sha256 `9d8c3d5b...`, reproduced byte for byte by two
independent runs): **no rule-exit passes development** (0 of 768). All 704 rule-exits with at least 200 development
trades have a negative mean net return (the median of those means is -2.9%; 16 are positive before costs, the best
+0.43%). Validation is similar (median of rule-exit means -2.7%; 5 of 768 positive, as noise would give; none of them
passed development). The leveraged portfolio of the most-traded rule loses at every rung. The holdout was not read.
Coverage of the research package's verified +20% events is 83.8% (labelled survivorship-limited). Wave H: 62.9% of
>= 100% gainers were already +20% at 09:25 (69.7% without basis-uncertain rows; the package says 77%); Spearman of that
gain with the eventual gain 0.26 (package: 0.04). The >= 10x degree tier is mostly price-basis artifacts (62 days, 16
clean; D6), so its capture numbers are reported with and without those rows.

## Result (v2, development and validation)

`evidence/summary-v2-dev-val-run-v1.json` (results sha256 `3334962f...`, two independent runs byte-identical): **no
rule-exit passes development in any family**, so nothing validates and no holdout is read.

- **E, first-cross (earliest-stage) entries**: all 216 rule-exits have negative mean net returns (median -3.1%); none
  is positive even before costs. Entering at the first minute a mover qualifies does not help: the average qualifier
  fades from there.
- **F, follow-up setups**: all 16 negative net; the best is the 15-minute opening-range breakout with its range-low
  stop (Y2), -0.34% net, +0.31% before costs.
- **P, pre-positioning at the previous close**: all 12 negative net (best -1.0%). The volume-breakout score's
  qualifying set holds 11.7% of the next day's >= +100% movers against a 0.004% base rate: it locates where extreme
  movers come from, but the average selected name still loses after costs.

## Pipeline and how to reproduce

Runtime pinned by the protocol: Python 3.12.3, duckdb 1.5.5, numpy 2.5.3 (the adaptive-paper tools environment on this
PC). Inputs are private (SIP terms) and must be re-collected on a new host with its own Alpaca market-data login; the
committed hashes tell you whether a re-collection matches.

| Step | Command (paths are placeholders) | Output |
| --- | --- | --- |
| candidates | `candidates.py --daily DAILY --out candidates-provable.csv` | daily-high superset (sha pinned in protocol.json) |
| intraday data | `collect.py --env-file ENV --candidates CSV --out DIR --asof 2026-09-21` (D2) | bars, auctions, news pages + ledger |
| pre-market superset | `premarket_scan.py ... --out DIR`, then `--finalize candidates-premarket.csv` (D3) | supplement (sha pinned in D3) |
| signals | `features.py signals --daily DAILY --split dev --out F` | pre-entry fields only |
| cost table | `quotes.py sample`, `quotes.py fetch`, `quotes.py table` (development only) | `evidence/cost-table-run-v1.json` |
| outcomes | `features.py outcomes --split dev|val --cost-table evidence/cost-table-run-v1.json` | gated on the table's sha |
| v1 results | `evaluate.py dev_val ...`; holdout only with `--dev-val` results and validated rule-exits | results + `summarize.py` |
| v2 | `features_v2.py --split dev|val --cost-table ...`, `evaluate_v2.py dev_val ...` | E, F, P families |
| live scan | `mover_scan.py --env-file ENV --rule "08:00|G0.20|V250000|any" --pages DIR --out scan.json` | the paper trial's universe |
| paper vs model | `paper_compare.py --scan scan.json --fills fills.json --exit X2 ...` | fill differences in bps |

Every page read is checked against its ledger's sha256; outputs are byte-identical across runs. Synthetic tests:
`tests/test_mover_early_entry_*.py`, `tests/test_mover_followup_v2.py` (skipped without numpy).

## Files

| File | Role |
| --- | --- |
| `rules.py` | the protocol definitions as pure functions (entries, exits, halt flag, cost buckets, dated fees, net returns) |
| `features.py`, `features_v2.py` | per-symbol-day signals, outcomes and v2 trades from the ledgered collections |
| `quotes.py` | development-only cost sample, SIP quotes and the cost table |
| `evaluate.py`, `evaluate_v2.py`, `summarize.py` | statistics, selection, capture, replication, gates, leveraged portfolio; public summary |
| `candidates.py`, `collect.py`, `premarket_scan.py`, `benchmarks.py`, `sessions_io.py` | data collection and readers |
| `mover_scan.py`, `paper_compare.py` | live scanner (same rules as the study) and the paper-versus-model comparison |
| `fees.json` | SEC Section 31, FINRA TAF and IBKR tiered rates from primary sources, dated |

All collected data and per-trade results stay private. Only aggregate results and hashes are committed.
