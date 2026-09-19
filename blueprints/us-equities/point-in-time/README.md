# Temporal snapshot and selection contract

Native DuckDB **1.5.5** wrote a synthetic normalized dataset to two Parquet files,
then queried six explicitly scoped selections. Four additional CLI attempts
rejected missing availability, overwrite, corrupted snapshot data and excessive
timestamp precision. The [receipt](receipt.json) records all **11 command exits**, artifact hashes and
selected source/universe row IDs. The [fixture](fixture.json) is synthetic: its
100-to-90 amendment illustration extends the existing financial-data test.
It is not SEC data, an entitled vendor dataset, broker input or accepted trading data.

| Decision cutoff | Selected synthetic values, feed A / raw / selected universe |
| --- | --- |
| February 10, 2025 | AAPL 100; MSFT 200 |
| March 10, 2025 | AAPL 90; MSFT removed by the known effective universe change |
| April 10, 2025 | AAPL 90; SPY 300, after its preannounced universe addition becomes effective |
| February 10 replay | AAPL 100; MSFT 200, exactly as before |

The other feed returns its separate AAPL value 999; the split-adjusted selection
returns 50. These deliberately different synthetic values demonstrate scope
separation, not an actual adjustment or feed-quality comparison. A ZZZ record
belongs only to another named universe and is excluded from these selections.

## Contract and evidence boundary

The [selector](select.sql) requires cutoff, universe, feed, adjustment, field and
unit. It filters availability and event/effective time before selecting the
latest eligible state/revision. Semantic revision ties are rejected during
snapshot creation rather than broken by row order. Stable `asset_id` values are
distinct from display symbols; their actual provider mapping remains unverified.

| Timestamp or reference | Meaning in this contract |
| --- | --- |
| `event_at` | Time of a realized observation; future observations are excluded |
| `effective_at` | Time a universe membership state takes effect; an earlier announcement does not activate it early |
| `available_at` | Declared earliest decision eligibility, with an explicit basis and evidence reference |
| `first_observed_at` | Original capture/observation time asserted by the source record, distinct from ingestion here |
| `availability_basis=captured_observation` | Requires availability at or after that original capture time; a current capture cannot reconstruct prior historical knowledge |
| `availability_basis=source_publication` | Allows evidenced historical publication to predate later observation/download; this utility preserves the assertion but does not authenticate it |
| Snapshot `ingested_at` | When this local snapshot was materialized; it does not replace source publication time |
| `adjustment_available_at` and `adjustment_reference` | Availability cannot precede the declared adjustment evidence; the utility does not compute or authenticate corporate-action adjustments |

The MSFT fixture deliberately declares publication in 2025 and observation in
2026. Its eligibility tests the separate timestamp meanings; output explicitly
reports `availability_evidence_authenticated=false` and `entitlement_verified=false`.
A production input needs independently supported availability and adjustment
evidence. Merely filling these fields does not supply it.

`temporal_snapshot.py` reuses timestamp, strict JSON, hashing and exclusive-write
primitives from [the existing SEC workflow](../financial-data/sec_data.py).
It does not duplicate its SEC parser or acquisition logic. Values retain their
source decimal strings and also enter DuckDB as `DECIMAL(38,12)` without rounding.
Decimal exponents are bounded to -12 through 25, including zero-valued inputs,
so a zero with an enormous exponent cannot reach the native conversion layer.
Duplicate JSON keys, nonfinite/unrepresentable values and timezone-free timestamps
are rejected. Source timestamps and decision cutoffs must use RFC3339 with at most
six fractional digits. Sub-microsecond timestamps are rejected, including a
nonzero seventh digit, because truncation could move an observation across a cutoff.

Snapshot creation reserves a new directory, preserves source bytes and publishes
the manifest last. Existing output is never replaced. A partial failure leaves an
unaccepted directory without a complete manifest. The caller must retain the
returned manifest SHA-256 independently. Selection checks that digest and every
data-file hash, then queries private copies of those exact verified bytes.
The file permissions deter accidental edits; they do not provide immutable media,
signatures, independent key custody or off-host recovery.

## Replay with the existing native SDK environment

Use the [accepted SDK lock](../../../adoption/sdk/requirements-linux-x86_64-py313.lock)
and its installed Python. Set `STACK_REPO`, `SDK_PYTHON`, and a new private
`PIT_RUN` directory outside Git. No package, provider or account change is needed.

```sh
umask 077
mkdir "$PIT_RUN"
"$SDK_PYTHON" "$STACK_REPO/blueprints/us-equities/point-in-time/temporal_snapshot.py" snapshot \
  --source "$STACK_REPO/blueprints/us-equities/point-in-time/fixture.json" \
  --output "$PIT_RUN/snapshot" > "$PIT_RUN/snapshot-result.json"
SNAPSHOT_SHA256=$("$SDK_PYTHON" -c \
  'import json,sys; print(json.load(open(sys.argv[1]))["snapshot_sha256"])' \
  "$PIT_RUN/snapshot-result.json")

"$SDK_PYTHON" "$STACK_REPO/blueprints/us-equities/point-in-time/temporal_snapshot.py" select \
  --snapshot "$PIT_RUN/snapshot" --snapshot-sha256 "$SNAPSHOT_SHA256" \
  --cutoff 2025-02-10T00:00:00Z --universe-id fixture-selected \
  --feed fixture-feed-a --adjustment raw --field Assets --unit USD
```

Repeat selection with March 10 and April 10 to reproduce the table. Output
retains original row IDs, universe provenance, exact value strings and the SQL
hash. A new snapshot has a new ingestion timestamp and manifest digest; use the
digest from that run rather than replaying the historical digest in the receipt.

The executed upstream APIs are `duckdb.connect`, typed SQL `INSERT`,
`DuckDBPyRelation.write_parquet`, `read_parquet`, and parameterized SQL execution.
The SQL file is the complete selection query; no external service or mock adapter
stands between it and DuckDB. From the repository root, run the regression checks:

```sh
"$SDK_PYTHON" -m unittest tests.test_point_in_time -v
```

All 13 checks passed in the existing native SDK environment. A Python environment
without DuckDB reports these as skipped, which does not establish acceptance.

## Remaining data gates and primary references

This validates a temporal selection mechanism on synthetic data. Real data still
needs source rights, recorded publication/ingestion evidence, historical universe
and identifier coverage, correction/cancellation semantics, corporate actions,
feed consistency, freshness/completeness checks and independent reconstruction.
An effective-dated universe selector is not a generic processor for preannounced
future corporate actions or forecasts. No profitability, strategy validation,
live broker reconciliation or operational trading readiness is established.

- [DuckDB temporal joins](https://duckdb.org/docs/current/guides/sql_features/asof_join)
  documents nearest-preceding temporal lookup. This query adds separate availability,
  universe and revision filters because a timestamp join alone cannot validate them.
- [DuckDB Parquet overview](https://duckdb.org/docs/current/data/parquet/overview)
  documents native Parquet reading/writing and SQL integration.
- [Alpaca market-data FAQ](https://docs.alpaca.markets/us/docs/market-data-faq)
  distinguishes source feeds and explains that historical `asof` controls symbol
  mapping. That parameter is not evidence of what a research system knew at a
  historical decision time. No Alpaca endpoint was called in this acceptance.
