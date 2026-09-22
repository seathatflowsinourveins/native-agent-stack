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
  pandera==0.33.1 pandas exchange_calendars==4.13.2 pyarrow
"$GATE_TOOL_DIR/.venv/bin/python3" promotion_gate.py \
  --input snapshot.parquet --out gate-result.json [--calendar XNYS]
```

Resolved versions from the actual native install used to build and test this
gate: `pandera==0.33.1`, `pandas==3.0.6`, `pyarrow==25.0.1`,
`exchange_calendars==4.13.2`, on CPython 3.13.15 (`uv` resolved `pandas` and
`pyarrow` to their current majors; only `pandera` and `exchange_calendars`
were pinned by the caller).

It validates `--input` (a `.parquet` file, a `.csv` file, or a
`duckdb://<db-path>#<table>` spec -- the `duckdb` package is optional and not
part of the pinned install above, so that path is source-only until a caller
adds the dependency) against a pandera schema: rows unique on
`(symbol, session)`; `session` a valid trading session on the selected
`exchange_calendars` calendar; `open`/`high`/`low`/`close` all `> 0`;
`high >= max(open, close)`; `low <= min(open, close)`; `volume >= 0`;
`observed_at <= now`. It writes `gate-result.json`:
`{status: "pass"|"fail", input_sha256, row_count, checks: [{name, status,
detail}], versions, checked_at}`. Any exception -- schema failure or an
unreadable/malformed input, a missing dependency, an unknown calendar code --
produces `status: "fail"` with the raised exception's class name; the gate
never raises past its own `main()`. Two synthetic fixtures live under
`fixtures/` as CSV (`.csv`, not `.parquet`: `scripts/validate.py`'s
publication scan requires every non-PNG/PDF file to decode as UTF-8 text, and
Parquet is binary) -- `good.csv` passes every named check; `bad.csv` fails
`valid_trading_session`, `volume_non_negative`, `observed_at_not_future`,
`high_ge_max_open_close` and `unique_symbol_session` by construction) with
their retained gate outputs (`fixtures/good-gate-result.json`,
`fixtures/bad-gate-result.json`). `tests/test_promotion_gate.py` reruns both
through the isolated venv.

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
snapshot_path=args.snapshot)`. The gate must report `status: "pass"` and an
`input_sha256` matching `--snapshot`'s current sha256, or the runtime raises
`SafetyError` with kind `promotion_gate_missing` (no result file, no
snapshot path, unreadable/invalid JSON), `promotion_gate_failed`
(`status != "pass"`), or `promotion_gate_mismatch` (hash does not match the
current file). `mode=None` (the `preflight` and `recover` call sites) is
unaffected. `--snapshot` must name an actual bars/universe input file that
was run through `promotion_gate.py` -- this repository does not yet ship a
production bars/universe ingest that produces one; until that ingest exists,
an operator must supply the real file it will produce (or, for the bounded
CSV fixtures used in tests here, `fixtures/good.csv` with
`fixtures/good-gate-result.json`).
