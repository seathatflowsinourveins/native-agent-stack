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

## Run 2026-09-29 (`asof-20260929`)

The committed record is `evidence/summary-asof-20260929.json` (totals only; each private file by sha256).

**E1, the primary estimand, did not run.** The gate refused with `inputs_missing` and sent no request, because the
three pinned private inputs (audit results `7e8b6999…`, main candidates `afe22552…`, pre-market supplement
`e8ea2dc3…`) are not on this host. This run therefore reports no `(498 + recovered) / 594` figure, and no reason
class for any of the 96 missed events. E1 needs those three files copied into the run's `inputs/` with their sha256
checked. After that it needs one `gate`, `fetch`, `classify` and `classify --verify` run.

**E2, the secondary estimand, ran.** The run used the transient user unit `asof-20260929-e2` (CPUWeight=20, Nice=10,
MemoryMax=8G, paper key pair 1, market data only).
- The unit finished with result success and exit status 0, in 4 min 21.8 s and 18.4 s of CPU. systemd printed a
  memory peak of 1016.0K, which is implausibly low for this workload and is not treated as a measurement. A probe
  unit showed that the unit cgroup's `memory.max` and `cpu.weight` do apply.
- It sent 3,585 requests, all HTTP 200, and no leg ended in an error. The control was sent at 02:11:45Z (22:11 ET on
  2026-09-28).
- A second classify on the same snapshots was byte-identical.
- The fetch ran at code revision `291c9909`, from a clean tree. After the first classify, the post-hoc
  outside-N2 total was added in `2f32494f`. In `99dfec7c` the classify revision moved from `summary.json` to
  `verify.json`, so the classify outputs depend on the snapshots alone. Classify and verify were then rerun offline at
  `99dfec7c` on the unchanged snapshots: `results.json` and `labels.json` came out byte for byte as the unit's own
  classify, and only `summary.json` gained the new total.

| Measure (E2) | Result |
|---|---|
| Package events dated 2021-01-04..2025-12-31 | 715 |
| N2: new-vintage v2 `match` or `recovered_match` with a gain of at least 20% | 594. By tier: 23, 64, 246, 214, 43 and 4, the committed counts exactly (N2 - 594 = 0 in every tier) |
| Frozen candidate rule on the as-of F1 bars, among N2 | 594 touch passes, with no derivative, missing-row or below-touch case |
| F2 (the event's own symbol, as of 2026-09-21) on d, among N2 | same issuer 594, other issuer 0, no row 0 |
| F2 outside N2 (post hoc, the other-issuer side of the same test) | same issuer 115, other issuer 4, no event data 2 |
| Package verdicts in the new vintage | 395 match, 202 recovered_match, 67 mismatch, 43 recovered_mismatch, 6 no_prev_close, 2 no_source_data |
| Flags among N2 | 14 basis-uncertain, 3 OTC as known, no gap over 7 days |
| Positive control | KOD and LFCR both fire the touch rule: passed |
| Exposure | 979 of 155,642 price rows fall before 2021-01-04 (lookback into 2020); none falls in 2026-01-02..2026-09-18 |

What E2 shows: on the rederived set, a daily re-fetch keyed by each event's own symbol with `asof` = the event date
places every N2 event in the frozen candidate superset. The event's own symbol, queried as of 2026-09-21, still
returns the same issuer's bar on d for every N2 event. So neither the touch rule on as-of data nor a reused ticker
accounts for any N2 event. The identity test can also report the other side: outside N2 it returned another issuer
for 4 events.

What E2 does not show: it cannot identify the 96 missed events or measure E1's coverage. N2 matches the committed 594
tier by tier, but E2 cannot show that it is the same set of events. Three explanations for the 96 remain open:
- a rename, where the frozen daily rows sit under a successor symbol that `coverage()` never keys
  (`recovered_keyed_under_successor`);
- a rename that splits the rows on the event date;
- a collection step: asset-list enumeration, today's OTC exclusion, placeholder symbols or identity dedup.

Separating them needs E1 and, for the collection steps, the private daily dataset (plan `not_measured`).
