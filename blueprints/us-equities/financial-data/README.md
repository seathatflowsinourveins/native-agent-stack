# SEC financial-data research lane

This small native recipe acquires official SEC JSON, preserves immutable source
snapshots, writes exact numerical facts to Parquet with DuckDB, and emits a cited
packet for the existing Astra and Claude research workers. It adds no agent
framework, document embedding service, market-data feed, or broker connection.

**Current live acceptance: blocked at the first SEC request with HTTP 403.** The
attempt was retained and stopped without retries. No live SEC payload, Parquet
dataset, or ready factual packet was produced. The separate offline tests exercise
the real DuckDB and packet commands with explicitly artificial fixtures; they are
not evidence that the SEC acquisition succeeded. See [receipt.json](receipt.json).

## Source and availability contract

The SEC supplies submissions metadata and company facts through public JSON APIs.
Its submissions response contains recent filing records; older records can be
listed in additional files. Company facts covers standard-taxonomy, entity-wide
facts rather than every disclosure or narrative passage. This recipe deliberately
fetches only the two current endpoints for each illustrative company.
[SEC API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)

The four requests select **AAPL and MSFT as illustrative documents**, not as a
trading universe. Normalization retains USD and other reported units for four
concepts: Assets, Liabilities, StockholdersEquity, and NetIncomeLoss. The packet
selects USD only. Different periods and units are never silently combined.

- Raw JSON is addressed by SHA-256; its source URL, fetch completion time, and
  first local observation are retained. Identical bytes reuse their original
  first-observation metadata. New payloads create new snapshots.
- Each numerical row retains accession, reported unit, exact decimal text,
  fiscal year/period, start/end, form, amendment flag, JSON pointer and both
  source hashes. Decimal storage is `DECIMAL(38,12)`; unrepresentable values fail
  closed instead of being rounded. No LLM computes the financial values.
- Availability is `max(acceptance_at, first_observed_at)` using the later first
  observation of the companyfacts and submissions snapshots. Acceptance requires
  an explicit timezone and an unambiguous accession join with matching form and
  filing date. Missing, conflicting or invalid metadata excludes the row.
- Raw versions are preserved. Packet selection chooses the latest eligible
  acceptance for the same concept/unit/start/end. Conflicting latest values are
  excluded. A `/A` form is marked as an amendment; the API does not establish an
  explicit supersedes relationship, and this recipe does not invent one.
- From those comparable reports, the packet picks the latest period end and
  then latest start per symbol/concept. Duration is explicit; it does not label a
  shorter period as annual or calculate growth across incompatible periods.

**Today's API payload cannot establish what this system knew years ago.** Newly
observed snapshots are unavailable to earlier cutoffs. This conservative design
also delays previously known individual facts when their containing snapshot
changes. It favors avoiding leakage over reconstructing their earliest possible
availability. It assumes the host clock is accurate. It does not yet track later
withdrawals as tombstones across snapshots, implement continuous ingestion, fetch
older submission files, or build a licensed historical point-in-time database.

## Run with upstream Python and DuckDB

Use the research environment pinned in [workers/requirements.txt](../workers/requirements.txt),
which already declares `duckdb==1.5.5`. Set `RESEARCH_PYTHON` to its Python executable,
`STACK_REPO` to this checkout, and `FINANCIAL_DATA_ROOT` to a private data directory.
Do not point it at an account/configuration store or a public repository.

Provide an honest `SEC_USER_AGENT` identifying the real project and a contact.
The SEC illustrates a company name and administrator email, requests declared
agents, and sets an overall ten-requests-per-second guideline. This recipe uses
one sequential writer, at most two request starts per second, and no automatic
retry. It cannot coordinate other applications using the same network.
[SEC access guidance](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)

```bash
"$RESEARCH_PYTHON" "$STACK_REPO/blueprints/us-equities/financial-data/sec_data.py" acquire \
  --root "$FINANCIAL_DATA_ROOT" --run-id first-observation
```

`SEC_USER_AGENT` is read from the environment, so it need not appear in a command
history. No identity is invented by the recipe. The native attempt used the real
project's public URL as its contact and returned 403; this alone does not establish
the reason for SEC's rejection. Do not retry an unchanged refusal repeatedly.

Each successful response is bounded at 25 MiB, with a 20-second socket timeout
and elapsed-deadline checks between reads. DNS and operating-system I/O behavior
can extend wall time; the supervising runtime must impose its own task timeout.
Redirects, non-JSON responses, compressed bodies, malformed JSON, oversized and
incomplete bodies are refused. Complete source snapshots can survive a later
failed request, but a failed run never publishes a completed dataset receipt.

On a completed acquisition, read the receipt's `as_of` into `AS_OF`. The following
offline command verifies the Parquet hash and applies the cutoff:

```bash
"$RESEARCH_PYTHON" "$STACK_REPO/blueprints/us-equities/financial-data/sec_data.py" packet \
  --run "$FINANCIAL_DATA_ROOT/acquisitions/first-observation" --as-of "$AS_OF" \
  --out "$FINANCIAL_DATA_ROOT/packet.json" --text-out "$FINANCIAL_DATA_ROOT/packet.md"
```

Existing snapshots, run directories, packets and Parquet files are never
overwritten. Use a new run name for a justified subsequent acquisition. Files are
published only after full writes and filesystem synchronization. The completed
receipt is the run's commit marker; an interrupted directory without it is not an
accepted dataset. This is local integrity and restart behavior, not a backup or
multi-host transaction system.

The upstream DuckDB operations are ordinary `INSERT`, `COPY ... (FORMAT PARQUET,
COMPRESSION ZSTD)`, and `SELECT ... FROM read_parquet(?)`. No custom storage engine
is introduced. [DuckDB Parquet documentation](https://duckdb.org/docs/stable/data/parquet/overview)

## Research worker interface

The JSON and text packets are each capped at 8,192 bytes. Each fact has a unique
`citation_id` (`F1` through `F8`) and a `source_id` pointing to `sources[*].id`
(`S1`, etc.). `numerical_facts[*].value` is an exact decimal **string**, separate
from prose. Sources include SEC filing links, accessions, hashes and observation
times. Filing HTML is not fetched; workers must not imply they read its narrative.

Top-level `status: ready` requires every AAPL/MSFT × four-concept pair to survive
the cutoff and unit/ambiguity checks. Anything missing produces `incomplete` and
exit code 2. A failed acquisition or integrity check exits 1. The host runtime
must gate model work on both exit 0 and `status: ready`; a schema-valid incomplete
packet is not permission to substitute model knowledge. Research reports should
cite fact IDs, preserve `as_of`, state missing evidence, and never authorize trades.

This is bounded financial-data retrieval. It does not claim complete financial
RAG, predictive value, equivalent-quality provider token savings, or that an
unrelated LEAN baseline used these facts.

## Verification

```bash
"$RESEARCH_PYTHON" -m unittest tests.test_financial_data
python3 scripts/validate.py
python3 -m unittest
```

Run from the checkout. The first command exercises temporal leakage, amendments,
ambiguous acceptance, currency mismatch, full decimal precision, interrupted
downloads, partial acquisition, source corruption, non-overwrite behavior, and
the actual Parquet/packet CLI. The base-Python suite skips the two DuckDB checks
when the pinned dependency is absent; that skip is not native data acceptance.
