# Deterministic data before model context

The executed example reads the native LEAN sample's six order events, selects
the useful fields, writes Zstandard Parquet, reopens it with DuckDB and computes
counts. `exchange-calendars` supplies the sample session's XNYS open/close times.
These are simulated historical events, not a broker feed or a strategy result.

With the [SDK environment](../workers/README.md) installed:

```sh
"$SDK_ENV/bin/python" "$STACK_REPO/blueprints/us-equities/data/summarize_backtest.py" \
  "$LEAN_SOURCE/Launcher/bin/Debug/BasicTemplateFrameworkAlgorithm-order-events.json" \
  "$PRIVATE_RUN_DIR/order-events.parquet"
```

The resulting receipt contains only counts, time boundaries and file hashes.
The selected Parquet stays private. Arithmetic uses SQL decimal fields. Do not
feed full bars, ticks or whole order logs into model prompts when a source-linked
aggregate answers the question. This reduction is a data-processing decision;
no unmeasured provider token saving is attributed to it.

For a real data ingest, retain vendor/feed entitlement, event and receive times,
UTC timezone, corporate actions, adjustment mode, symbol history, universe as of
date, source revision and missing-data status. Query as of the research cutoff.
Keep immutable inputs and strategy/version hashes with each backtest. Use
out-of-sample periods, costs and market-calendar rules before comparing research
results. This example does not implement that full production ingest.

Upstream: [DuckDB Python](https://duckdb.org/docs/stable/clients/python/overview),
[Parquet](https://duckdb.org/docs/stable/data/parquet/overview),
[exchange_calendars](https://github.com/gerrymanoim/exchange_calendars).

## Fail-closed promotion gate

`promotion_gate.py` is a standalone CLI, run in its own isolated environment
separate from the paper runtime:

```sh
uv venv "$GATE_TOOL_DIR/.venv"
uv pip install --python "$GATE_TOOL_DIR/.venv/bin/python3" \
  pandera==0.33.1 pandas exchange_calendars==4.13.2 pyarrow duckdb==1.5.5
"$GATE_TOOL_DIR/.venv/bin/python3" promotion_gate.py \
  --input snapshot.parquet --out gate-result.json [--calendar XNYS]
```

Resolved versions from the actual native install used to build and test this
gate: `pandera==0.33.1`, `pandas==3.0.6`, `pyarrow==25.0.1`,
`exchange_calendars==4.13.2`, on CPython 3.13.15 (`uv` resolved `pandas` and
`pyarrow` to their current majors; only `pandera` and `exchange_calendars`
were pinned by the caller). The hash-locked install is
`uv pip sync --require-hashes requirements.lock`; `duckdb==1.5.5` was added
to `requirements.in` and the lock recompiled with uv 0.12.17, which moved no
other pin.

It validates `--input` (a `.parquet` file, a `.csv` file, or a
`duckdb://<db-path>#<table>` spec; `duckdb==1.5.5` is pinned in
`requirements.lock` since 2026-09-23; the wave-2 receipt reproduced five CSV
fixtures through DuckDB tables, see
[the wave-2 receipt](../../../evidence/artifacts/gap-wave2-20260923/us-equities__data-quality-orchestration/5-duckdb-gate-input.json),
and `DuckdbInputRuns` in `tests/test_promotion_gate.py` now also covers
`lossy-volume-conversion.csv` with an exactly stored `volume`) against a pandera schema plus two checks computed
outside pandera: the snapshot has at least one row (`rows_present`; a
0-row snapshot with every required column present fails closed instead of
reporting `status: "pass", row_count: 0`), rows unique on `(symbol, session)`;
`session` a valid trading session on the selected `exchange_calendars`
calendar; `open`/`high`/`low`/`close` all `> 0`; `high >= max(open, close)`;
`low <= min(open, close)`; `observed_at <= now`; and `volume` is finite,
integral and `>= 0` (`volume_integral_non_negative`), validated on the RAW
column BEFORE any lossy numeric coercion -- a raw value like `-0.5` would
otherwise be silently truncated to `0` by a later `astype('int64')` and pass
a post-coercion `>= 0` check.

A recognized pandera failure is reported under its named check even when
pandera did not attach a row index to that failure case (e.g. the
`valid_trading_session` check calling `calendar.is_session()`, which raises
rather than returning `False` for an unparseable date, produces a
`failure_cases` row with `index: null`) -- `_summarize()` counts every
recorded failure case for a check regardless of index availability and
records `"row index unavailable"` in the check's `detail` when no index was
available for it, rather than silently reporting the check as "pass" (Codex
cross-family review finding, `codex-review-64`).

`volume_integral_non_negative` Decimal-parses the RAW `volume` cell's exact
source text with `decimal.Decimal` (rejecting non-finite values, negative
values including a `-0`/`-0.0` produced by a negative literal, any non-zero
fractional part, and values above int64 max) rather than converting through
`float`/`pd.to_numeric` first: a float round-trip is itself lossy for values
like `-1e-400` (underflows to `-0.0`, which then reads as non-negative and
integral) or `9007199254740992.5` (loses its fractional part once past
float64's ~15-17 significant digits), both of which silently passed the
gate's earlier float-based check (Codex cross-family review finding,
`codex-review-64`). The `.csv` loader reads every column with `dtype=str` so
`volume`'s exact source text survives to that Decimal parse; an integer
already read as int64 (a whole-number CSV cell, or a Parquet int64 column) is
exact either way and goes through `Decimal(int(...))`, never a float. A
Parquet `volume` column stores a typed float/int at write time, so this
exactness guarantee is CSV-only -- a lossy Parquet float `volume` cell falls
back to `Decimal(repr(value))`, a best-effort check on whatever precision the
Parquet writer already kept, not the source-text guarantee CSV gets.

A `duckdb://<db-path>#<table>` input (changed 2026-09-23 after Codex review of
PR #132) must name a BASE TABLE stored in the database file, checked through
`system.information_schema.tables.table_type` before any row is read (and a `<db-path>.wal` is checked again after the read): `input_sha256`
hashes only that file, so a view such as `SELECT * FROM
read_parquet('current.parquet')`, whose rows come from a mutable external
file, fails closed with `duckdb_relation_not_base_table`, and a pending
`<db-path>.wal`, whose changes a read-only open replays but the hashed file
lacks, fails closed with `duckdb_wal_present`. The gate reads the `volume`
column as DuckDB's exact VARCHAR rendering instead of `fetch_df()`'s float64:
a DECIMAL `9007199254740992.5` used to round to `9007199254740992.0` and pass.
A DECIMAL or VARCHAR `volume` therefore keeps the CSV exactness guarantee. The guarantee covers `volume` only: DECIMAL `open`, `high`, `low` and `close` values are read as float64, as the CSV path reads them. A
DOUBLE `volume`, including the type DuckDB's `read_csv` auto-detects for a
fractional column, has lost precision at write time, as a Parquet float has.
It writes `gate-result.json`:
`{status: "pass"|"fail", input_sha256, row_count, checks: [{name, status,
detail}], versions, checked_at}`. Any exception -- schema failure or an
unreadable/malformed input, a missing dependency, an unknown calendar code --
produces `status: "fail"` with the raised exception's class name; the gate
never raises past its own `main()`. Synthetic fixtures live under
`fixtures/` as CSV (`.csv`, not `.parquet`: `scripts/validate.py`'s
publication scan requires every non-PNG/PDF file to decode as UTF-8 text, and
Parquet is binary):

* `good.csv` passes every named check.
* `bad.csv` fails `valid_trading_session`, `volume_integral_non_negative`,
  `observed_at_not_future`, `high_ge_max_open_close` and
  `unique_symbol_session` by construction.
* `null-price-cell.csv` has a null `open` cell, which pandera reports under
  its own `not_nullable` identifier -- not one of the fixed `CHECK_NAMES` --
  so it surfaces as a synthetic `unmapped_failures` check rather than being
  silently absorbed into any named check passing.
* `empty-snapshot.csv` (header row only, 0 data rows) fails only
  `rows_present`; every other check reports "pass" over the empty frame
  (Codex cross-family review finding, PR-4 follow-up).
* `fractional-negative-volume.csv` has one row with raw `volume=-0.5`; it
  fails only `volume_integral_non_negative` (Codex cross-family review
  finding, PR-4 follow-up).
* `null-index-session.csv` has one row with `session=not-a-date`, whose
  `valid_trading_session` pandera failure case carries `index: null`
  (`calendar.is_session()` raises rather than returning `False`); it fails
  only `valid_trading_session`, with `"row index unavailable"` in that
  check's detail (Codex cross-family review finding `codex-review-64`).
* `lossy-volume-conversion.csv` has raw `volume` values `-1e-400` and
  `9007199254740992.5`, both of which a float-based check silently passed;
  it fails only `volume_integral_non_negative` for both rows (Codex
  cross-family review finding `codex-review-64`).

Each fixture's retained gate output lives alongside it
(`fixtures/<name>-gate-result.json`). `tests/test_promotion_gate.py` reruns
every fixture through the isolated venv; `tests/test_promotion_gate_codex_review.py`
additionally covers the `null-index-session.csv` and
`lossy-volume-conversion.csv` regressions plus pure-stdlib unit tests for
`_summarize()`'s index-unavailable path and `_volume_cell_fails()`'s Decimal
parsing.

The gate runs in its own environment so the paper runtime
(`../adaptive-paper/runner.py`) never imports pandera/pandas/
exchange_calendars; it only reads the resulting `gate-result.json`. That
runtime has no live market-data snapshot concept of its own (Alpaca quotes
are fetched fresh at preflight time, not read from a stored file), and
`config.json` itself cannot be the gated "snapshot": `promotion_gate.py`
only accepts `.parquet`/`.csv`/`duckdb://` input, so pointing it at a JSON
config always fails closed with `unsupported_input_format`. Instead,
`runner.py`'s `main()` registers `--gate-result <path>` and `--snapshot
<path>` CLI arguments; for the `paper` command (not `preflight`, not
`recover`, which resumes a trial admitted by an earlier `paper` invocation)
it calls `validate_preflight(..., mode="paper", gate_result_path=args.gate_result,
snapshot_path=args.snapshot)`. The gate result must satisfy the full
contract -- every required key present, every named check passing,
`row_count > 0`, a top-level `status: "pass"`, and an `input_sha256` matching
a `--snapshot` file the gate itself could accept (`.csv`/`.parquet`) -- or the
runtime raises `SafetyError` with kind `promotion_gate_missing` (no result
file, no snapshot path, unreadable/invalid JSON, or an unusable/wrong-
extension snapshot path), `promotion_gate_incomplete` (a required key is
missing, or `checks` is missing/empty), `promotion_gate_failed_check` (a
named check reports `status: "fail"` despite a "pass" top-level status),
`promotion_gate_empty` (`row_count <= 0` despite a "pass" top-level status),
`promotion_gate_failed` (top-level `status != "pass"`), or
`promotion_gate_mismatch` (hash does not match the current file). `mode=None`
(the `preflight` and `recover` call sites) is unaffected. `--snapshot` must
name an actual bars/universe input file that
was run through `promotion_gate.py`. [`ingest_snapshot.py`](ingest_snapshot.py)
(added in #84) writes one: a bounded, read-only Alpaca daily-bar snapshot of
the adaptive-paper universe plus a receipt of counts and hashes, which
`../adaptive-paper/scheduled_trial.sh` gates before the `paper` command.
Trial `adaptive-20260923g` retained both results in
`../adaptive-paper/trials/20260923g-main-passed/` (`ingest-receipt.json` and
`gate-result.json`: 480 rows, gate `pass`, `input_sha256` equal to the
receipt's `snapshot_sha256`); the snapshot CSV itself was not retained. That
is one real ingest gating one paper trial, not the full production ingest
described earlier in this README. For the bounded CSV fixtures used in
tests here, use `fixtures/good.csv` with `fixtures/good-gate-result.json`.
