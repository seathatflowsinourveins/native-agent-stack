# Exact nanosecond replay acceptance

The existing locked **pandas 3.0.6 and DuckDB 1.5.5** preserved synthetic source
timestamps through typed integer columns, Parquet and hash-verified replay.
The [receipt](receipt.json) records **10 native command exits**: materialization,
five selections and four expected rejections. No package, account or provider
was added. This does not ingest market data or execute a strategy.

| Cutoff suffix after `2025-02-01T21:00:00` | Eligible source rows / values |
| --- | --- |
| `.000000099Z` | None |
| `.000000100Z` | Original / 100 |
| `.000000200Z` | Correction / 90; newly effective member / 200 |
| `.000000201Z` | Higher source sequence at the same available time / 85; member / 200 |
| Replay `.000000100Z` | Original / 100 again |

All five decision cutoffs lie inside one microsecond. Excessive timestamp
precision, int64 overflow, overwrite and corrupted Parquet each returned exit 2.
The [12 regression checks](../../../tests/test_nanosecond_replay.py) also cover
timezone equivalence, exact signed bounds, every timestamp field, ambiguous ties,
late universe removal, feed isolation and native `BIGINT` storage.

## Why integer nanoseconds

DuckDB documents microsecond `TIMESTAMPTZ` and nanosecond, timezone-naive
`TIMESTAMP_NS`; timezone-aware nanosecond Parquet columns can lose precision when
converted to `TIMESTAMPTZ`. The representation here deliberately uses **signed
UTC nanosecond BIGINT columns**, keeping the original timestamp text alongside
them. SQL eligibility and ordering never pass through floating-point epochs or
Python `datetime` objects. [DuckDB timestamp types](https://duckdb.org/docs/current/sql/data_types/timestamp)

The upstream parser is `pandas.Timestamp(...).tz_convert("UTC").as_unit("ns",
round_ok=False).value`, preceded by an explicit RFC3339 grammar. Accepted values
have an explicit offset and zero through nine fractional digits. The supported
inclusive UTC range is `1677-09-21T00:12:43.145224193Z` through
`2262-04-11T23:47:16.854775807Z`; the int64 minimum is excluded as pandas' NaT
sentinel. Finer precision, impossible dates, leap seconds, missing offsets and
range overflow reject. [pandas Timestamp](https://pandas.pydata.org/docs/reference/api/pandas.Timestamp.html)

Output JSON represents nanoseconds and source sequence as decimal strings so
ordinary JavaScript consumers cannot round them through IEEE-754 numbers.
Input JSON sequence integers require a lossless parser; the existing SEC strict
JSON parser supplies that here. Prices are opaque value strings in this narrow
acceptance, with no arithmetic, return or adjustment claim.

## Scope and integrity

[replay.py](replay.py) reuses the existing [PIT](../point-in-time/temporal_snapshot.py)
bounded-read, validation/error and SEC JSON/hash/exclusive-write primitives.
It adds a small synthetic event/revision schema, not another SEC or market parser.
The earlier microsecond PIT contract keeps its original supported scope.

Each observation has stable asset/event identity, a declared source sequence,
event time and original availability time. Revisions of one logical event retain
its event timestamp. Availability cannot precede a realized event. A sequence
breaks ties only within that asset/event/feed and available-time scope; equal
sequence ties reject. This does not establish cross-feed ordering or verify the
source's sequence/clock. A real ingestion adapter still needs source identity,
transport capture, clock-quality and correction/cancellation semantics.

Universe availability and effective time are separate: an announcement can be
known before membership takes effect. Late removals cannot rewrite earlier
eligibility. Symbol mapping and an actual historical universe remain unaccepted.

Snapshot creation requires a new directory and preserves original JSON bytes,
two Parquet files and a final manifest with hashes. Selection requires the
caller-held manifest digest, validates every file and queries private copies of
those verified bytes. Source and SQL hashes accompany each selection. File
permissions deter accidental writes; they are not immutable storage or off-host
recovery. Local ingestion time is metadata and never substitutes for historical
source availability. Every input is required to declare `synthetic=true`.

## Native replay

Use the existing [SDK lock](../../../adoption/sdk/requirements-linux-x86_64-py313.lock).
Set `STACK_REPO`, `SDK_PYTHON` and a fresh private `NS_RUN` outside Git:

```sh
umask 077
mkdir "$NS_RUN"
"$SDK_PYTHON" "$STACK_REPO/blueprints/us-equities/nanosecond-replay/replay.py" materialize \
  --source "$STACK_REPO/blueprints/us-equities/nanosecond-replay/fixture.json" \
  --output "$NS_RUN/snapshot" > "$NS_RUN/materialize.json"
NS_SHA256=$("$SDK_PYTHON" -c \
  'import json,sys; print(json.load(open(sys.argv[1]))["snapshot_sha256"])' \
  "$NS_RUN/materialize.json")
"$SDK_PYTHON" "$STACK_REPO/blueprints/us-equities/nanosecond-replay/replay.py" select \
  --snapshot "$NS_RUN/snapshot" --snapshot-sha256 "$NS_SHA256" \
  --cutoff 2025-02-01T21:00:00.000000100Z \
  --universe-id fixture-universe --feed fixture-feed
```

The native operations are pandas timestamp conversion, DuckDB typed `INSERT`,
`write_parquet`, `read_parquet` and the complete parameterized [SQL](select.sql).
A new materialization has a new ingestion timestamp and manifest hash: retain
the digest returned by that run. From the repository root:

```sh
"$SDK_PYTHON" -m unittest tests.test_nanosecond_replay -v
```

Environments missing pandas/DuckDB skip these checks, which is not acceptance.
The synthetic fixture does not prove data rights, original publication/receipt
authenticity, a +200% case census, real tick ingestion, factor quality, market
capacity, leverage, paper connectivity or live trading readiness.
