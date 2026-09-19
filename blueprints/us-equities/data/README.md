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
