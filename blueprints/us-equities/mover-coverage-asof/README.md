# Mover coverage: as-of re-fetch of the coverage misses

The mover-early-entry coverage gate counts 594 price-verified +20% events in 2021-01-04..2025-12-31, and the frozen
candidate set holds 498 of them (0.83838384, below the gate's 95% bar). `plan.json` asks how many of the 96 missing
events a daily re-fetch recovers when each event is keyed by its own symbol with `asof` = the event date and judged
by the frozen candidate rule, why each one was missing, and whether coverage then reaches 95%.

- `plan.json` is the preregistration. The commit that added it, before any request, is the freeze (plan sha256
  `5a5937e16f33c69e08034eb9f9bfb02acad05d2f8a929148e4d1c8bb3f2d9951`, 18,173 bytes). The runner records that sha256
  in every output and refuses to work under a different file.
- `refetch.py` is the runner. It reuses the price audit's client, official-close rule, gain, split factor, verdicts
  and package loader (`extreme-gainer-audit/audit.py`), `coverage()` and the degree tiers from mover-early-entry
  (`evaluate.py`, `rules.py`, loaded only when needed because they import numpy), the official-open rule
  (`sessions_io.py`) and the corporate-actions collector (`broad-universe/corporate_actions.py`).
- `evidence/` holds totals-only summaries. Per-event rows, symbols, dates, prices and label values stay in the private
  trial workspace (plan `guards.publication`).

## Subcommands

| Subcommand | Network | What it does |
|---|---|---|
| `gate --inputs DIR --out-dir RUN` | none | Checks the three private inputs by sha256, reproduces `coverage()` exactly, and writes the 96 missed and 498 control events. Missing or different inputs refuse the run and send nothing. |
| `fetch --env-file ENV --out-dir RUN` | market data | E1. Collects name changes first, then F1 (daily bars raw, split and all, and auctions, `asof` = d) and F2 (raw bars, `asof` = 2026-09-21) for the 594 events, plus the KOD/LFCR positive control. |
| `e2 --package-zip ZIP --env-file ENV --out-dir RUN` | market data | E2, the secondary estimand. It covers the package events dated 2021-01-04..2025-12-31, tries symbols in the audit's `load_events` order, and fetches F1, F2 and the control. |
| `classify --out-dir RUN [--verify]` | none | Applies the touch rule, reason classes, flags and labels. It writes private results and labels, and a totals-only `summary.json`. `--verify` recomputes all three and compares bytes. |
| `publish --run-dir RUN [--e2-dir DIR] --to FILE` | none | Writes the committed summary after a structural scan for paths, dates, symbol-like values and non-share numbers. |

Every request goes to the audit's fixed data host, on a `/v2/stocks/{symbol}/bars` or `/auctions` path. The whole
request plan is checked against the reserved holdout 2026-01-02..2026-09-18 before anything is sent. The control is
not sent before 20:00 ET on 2026-09-28. Pacing, the 429 retries after 1, 2 and 4 s, and the 400/404/422 handling are
the audit client's. Any request that ends in an error is recorded as an error, never as no data. No model is called.

## Run

`RUN` is the run directory `asof-20260929` in the private trial workspace (0700, files 0600). The paper-key wrapper
there hands its command a temporary 0600 env file in `PAPER_RAM_ENV`, and only the two key variables are read. The
unit reads market data only.

```sh
PY=<pinned adaptive-paper interpreter: Python 3.12.3, numpy 2.5.3>
R=blueprints/us-equities/mover-coverage-asof/refetch.py
"$PY" "$R" gate --inputs "$RUN/inputs" --out-dir "$RUN"          # E1 needs the three pinned inputs
systemd-run --user --wait --collect --unit=asof-20260929-e2 --working-directory="$WT" \
  -p Type=exec -p CPUWeight=20 -p Nice=10 -p MemoryMax=8G -p UMask=0077 -p NoNewPrivileges=yes \
  -p Restart=no -p KillMode=control-group -p RuntimeMaxSec=3600 \
  -E TMPDIR=/var/tmp -E PYTHONDONTWRITEBYTECODE=1 -E RUN="$RUN" -E PY="$PY" -E R="$R" \
  sh "<paper-key wrapper>" run 1 -- sh -c '"$PY" "$R" e2 --package-zip "$RUN/inputs/<package zip>" \
    --env-file "$PAPER_RAM_ENV" --out-dir "$RUN/e2" && "$PY" "$R" classify --out-dir "$RUN/e2" \
    && "$PY" "$R" classify --out-dir "$RUN/e2" --verify'
"$PY" "$R" publish --run-dir "$RUN" --e2-dir "$RUN/e2" --to blueprints/us-equities/mover-coverage-asof/evidence/summary-asof-20260929.json
```

For E1, copy the three inputs into `$RUN/inputs`, run `gate`, and then run `fetch`, `classify` and
`classify --verify` in the same kind of unit.

## Readings of the plan's text

These choices are made in the code and tested. They do not edit the frozen plan.

- **Decimal text.** Each snapshot keeps every response page as the provider's text. Labels parse it with
  `json.loads(parse_float=Decimal)` and decide each ratio flag with exact `Fraction`s. The audit's functions receive a
  float view instead: `float(Decimal)` rounds the decimal text once, as a JSON float parse does. The Decimal close and
  open selectors are checked at run time against `audit.official_close_v2` and `sessions_io.official_price`.
- **Touch.** The touch is computed in IEEE-754 double, as DuckDB computes `all_h >= 1.2 * prev_l`. For example, a low
  of 1.36 and a high of 1.632 fail the touch, although 1.632 is exactly 1.2 x 1.36 in decimal.
- **"An official close lies outside its daily bar's high-low range".** This is read as an auction-sourced official
  close (audit v2 rule, with the bar fallback excluded) of d or of the lag row that lies outside that day's raw bar
  low-high range.
- **`split_between`.** In the touch-failure branch it compares d with S's lag row, the touch's own prior row. For
  labels and `basis_uncertain` it is the one `audit.event_gain` computes against its previous close.
- **New-vintage gain.** The gain is computed only when the raw, split and auction legs all succeed. Otherwise it is
  undefined, and the event is flagged `leg_error` and `not_verified_in_new_vintage`.
- **Same issuer.** This means exact equality of the parsed raw `o`, `h`, `l`, `c` and `v` on d. A missing field
  counts as a difference.
- **Successor chain.** Each hop's process date comes after the previous hop's, the first after d, and none after
  2026-09-21.
- **E2.** Symbols are tried until one has a raw bar or an auction on d (audit `fetch`), and F2 is requested for that
  symbol only. The gain and verdict follow audit `compare`. Tiers come from the new-vintage gain. E2 collects no
  corporate actions, because none of its outputs uses them, so every E2 request stays outside the holdout window.
- **Symbol quoting.** Symbols are quoted with `safe=""`, so every symbol stays in one path segment.
- **Code revision.** `fetch` and `e2` refuse to run unless every file the run reads is tracked and unmodified, and
  they record HEAD.

## Tests

`TMPDIR=/var/tmp PYTHONDONTWRITEBYTECODE=1 <pinned python> -m unittest tests.test_mover_coverage_asof`. The 33 tests
are synthetic: made-up tickers, dates and prices, with no network, credential or private row. Five need numpy for the
degree tiers and are skipped without it.
