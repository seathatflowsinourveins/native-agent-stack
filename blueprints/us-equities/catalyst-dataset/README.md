# Offline SEC catalyst metadata dataset

## Design and input freeze — 2026-09-20

This wave converts an already acquired SEC daily index and five filing headers
into typed, queryable research metadata. It makes no network request, installs no
dependency and calls no model. The source day, deterministic acquisition subset
and temporal checks are fixed before execution; they are not selected by price
outcomes. This is not a historical point-in-time strategy dataset.

The accepted run is `native-format-confirmed-20260919`. Its immutable input
anchors are:

- Receipt SHA-256: `9d73682848321accbe95bac0f0fda50ebdef9851a693bfb8bdc6e8229a610e10`.
- Daily index: `2020-03-02`, 630238 bytes, SHA-256
  `5865f91e3d68590389b08760ea256fbaa1693fbc1b0e1350142fc3634a9c3383`.
- Expected cohort: 371 distinct `(CIK, accession)` rows, 360 accessions, 362
  `8-K` rows and 9 `8-K/A` rows. Five headers were fetched; 366 rows remain
  unfetched. Cofiling is preserved, not deduplicated by accession alone.
- Latest source observation: `2026-09-19T23:48:29.649862Z`. Acceptance timestamps
  are from 2020; they do not establish when this system received the information.

Stage A uses the existing EdgarTools **5.58.0** environment. It verifies the
externally supplied receipt hash and every declared blob, then reuses
`catalyst.packet()` and its current strict raw-header parser. It does not trust
the original receipt's stale `selected[].event` values. Native
`FilingHeader.parse_from_sgml_text()` supplies acceptance and repeated `ITEMS`;
`FilingSGML.from_text().header` supplies normalized form/accession/date and
structured filers. These are complementary views of the same verified bytes.
Any identity or acceptance disagreement fails closed. Native item titles come
from `EightK.structure.get_item()` and retain the parser version.

Stage B uses the existing DuckDB **1.5.5** environment. It requires the expected
Stage A manifest hash, verifies its exact payload set, and materializes typed,
sorted Parquet tables with native DuckDB SQL. The tables are `members`,
`headers`, and `items`; item identity is `(CIK, accession, header SHA-256, item
ordinal)`. A native SQL left join preserves unfetched rows with NULL header
metadata. The as-of filter requires qualified status and non-NULL availability
at or before the cutoff. Both historical and actual-observation cutoffs are
tested. Native timestamp types preserve UTC microseconds.

Every output directory must be new. Input/output paths containing symlinks or
parent traversal are refused. Manifests bind receipt/raw input hashes, local
bridge and upstream parser hashes, payload hashes, runtime versions and counts.
An externally supplied hash protects the next stage against a rewritten local
manifest; these are integrity anchors, not cryptographic source signatures.
Repeated materialization must yield identical Parquet bytes with the pinned
runtime. No acquisition is retried to obtain this result.

Known index observations are retained on every member. Unfetched rows have no
header acceptance, availability, item count or sentiment. `is_amendment` is
derived only from the form; `amends_accession` and `ticker` remain NULL. No price
join, adjusted-price assumption, ticker mapping, revision inference or return
label is introduced. Header item declarations are metadata, not proof of a
catalyst, its economic incentive or a trading signal. Item 9.01 may simply
identify exhibits.

## Primary sources and limits

- [EdgarTools 5.58.0 release](https://github.com/dgunning/edgartools/releases/tag/v5.58.0), MIT;
  installed execution is pinned to 5.58.0, not changing default-branch HEAD.
- [Pinned SGML header parser](https://github.com/dgunning/edgartools/blob/abe44344c56cf4bfb5443e0debca7e39342f6e7a/edgar/sgml/sgml_header.py)
  and [native current-report taxonomy](https://github.com/dgunning/edgartools/blob/abe44344c56cf4bfb5443e0debca7e39342f6e7a/edgar/company_reports/current_report.py).
- [Official Form 8-K](https://www.sec.gov/about/forms/form8-k.pdf): Items 5.02,
  7.01, 8.01 and 9.01 describe different reporting obligations. Native short
  labels are not a substitute for the full definitions; the 5.02 official title
  also includes compensatory arrangements, and 8.01 includes optional disclosures.
- [SEC webmaster FAQ](https://www.sec.gov/about/webmaster-frequently-asked-questions):
  acceptance and website availability differ. Our first observation is completion
  within this retained acquisition run, not a globally earliest receipt time.
- [DuckDB Parquet export](https://duckdb.org/docs/stable/data/parquet/overview.html)
  and [timestamp types](https://duckdb.org/docs/stable/sql/data_types/timestamp.html).

The SEC content is retained privately. The public receipt contains only bounded
metadata, hashes, exact commands and results. No monitored contact or raw filing
text belongs in the repository.

## Reproduction and acceptance

The [sanitized native receipt](native-receipt.json) records successful offline
execution. Native SQL independently confirmed:

| Check | Actual result |
|---|---:|
| Cohort identities / unique accessions | 371 / 360 |
| Cofiling groups / 8-K/A identity rows | 9 / 9 |
| Qualified observed headers / declared item links | 5 / 9 |
| Unfetched rows preserved with NULL header fields | 366 |
| Unknown ticker and amendment-parent mappings | 371 |
| Eligible headers / items at 2020-03-03 | 0 / 0 |
| Eligible headers / items at latest actual observation | 5 / 9 |

Item declarations were `5.02: 2`, `7.01: 2`, `8.01: 2`, `9.01: 3`. At the first
header's exact observation instant one header is eligible; one microsecond
before the last observation four are eligible; at that observation five are
eligible. This verifies the temporal boundary, not a tradable historical signal.
Both materializations produced identical bytes for all three Parquet tables
and their complete manifests. This is artifact determinism in the pinned
runtime, not a token-saving measurement.

The exact entrypoint is a repository contract bridge. The **upstream APIs** it
executes are:

```python
from edgar.sgml import FilingHeader, FilingSGML
from edgar.company_reports.current_report import EightK

tagged = FilingHeader.parse_from_sgml_text(verified_header_text)
normalized = FilingSGML.from_text(verified_header_text).header
accepted_naive = tagged.acceptance_datetime
declared_items = tagged.filing_metadata.get("ITEMS")
normalized_identity = (normalized.accession_number, normalized.form,
                       normalized.filing_date)
filers = [f.company_information.cik for f in normalized.filers]
label = EightK.structure.get_item("ITEM 5.02")
```

The tagged parser returns a timezone-naive acceptance value; the strict bridge
checks it against the original bytes and converts valid unambiguous Eastern
time to UTC. The normalized SGML view does not preserve acceptance or `ITEMS`
on these headers; the tagged view does not normalize their form/accession/date.
Neither API by itself provides this complete contract. `preprocess=True` and
URL-based `from_source()` are not used.

DuckDB's native `connect`, typed `CREATE TABLE`, parameterized `executemany`,
`COPY ... (FORMAT PARQUET, COMPRESSION ZSTD)` and `read_parquet` performed the
materialization and checks. The stored SQL uses `TIMESTAMPTZ` and an explicit
availability condition. For example, this upstream query returned `371, 360,
366`:

```sql
SELECT count(*) AS members, count(DISTINCT accession) AS accessions,
       count(*) FILTER (WHERE fetch_status='not_fetched') AS not_fetched
FROM members;
```

These are the accepted command templates from the repository root. Resolve the
four path variables to the existing EdgarTools Python, existing DuckDB Python,
retained accepted SEC run and new private output parent respectively. No provider
environment or contact is needed for offline conversion. Never point them at a
previous output directory.

```bash
"$CATALYST_PY" blueprints/us-equities/catalyst-dataset/dataset.py extract \
  --run "$ACCEPTED_SEC_RUN" --out "$DATASET_STATE/extraction" \
  --receipt-sha256 9d73682848321accbe95bac0f0fda50ebdef9851a693bfb8bdc6e8229a610e10

"$DUCKDB_PY" blueprints/us-equities/catalyst-dataset/dataset.py materialize \
  --extraction "$DATASET_STATE/extraction" --out "$DATASET_STATE/parquet" \
  --manifest-sha256 080b93378dc7dd866579efc3878be95b9a682f89013701465afa269d740b688c

"$DUCKDB_PY" blueprints/us-equities/catalyst-dataset/dataset.py materialize \
  --extraction "$DATASET_STATE/extraction" --out "$DATASET_STATE/parquet-repeat" \
  --manifest-sha256 080b93378dc7dd866579efc3878be95b9a682f89013701465afa269d740b688c

"$DUCKDB_PY" blueprints/us-equities/catalyst-dataset/dataset.py query \
  --dataset "$DATASET_STATE/parquet" --as-of 2020-03-03T00:00:00Z \
  --manifest-sha256 1447ea484822dd178084236e581a15e4c5659c84b25912c54281ca5029d9a792

"$DUCKDB_PY" blueprints/us-equities/catalyst-dataset/dataset.py query \
  --dataset "$DATASET_STATE/parquet" --as-of 2026-09-19T23:48:29.649862Z \
  --manifest-sha256 1447ea484822dd178084236e581a15e4c5659c84b25912c54281ca5029d9a792
```

The first command returned:

```json
{"manifest_sha256":"080b93378dc7dd866579efc3878be95b9a682f89013701465afa269d740b688c","stage":"extraction","summary":{"cofiling_groups":9,"headers":5,"items":9,"members":371,"not_fetched":366,"qualified_headers":5,"unique_accessions":360}}
```

Each materialization returned the same summary and manifest SHA-256
`1447ea484822dd178084236e581a15e4c5659c84b25912c54281ca5029d9a792`. The historical
query returned `eligible_count: 0`; the observation query returned
`eligible_count: 5`. Native output hashes and the additional boundary queries
are in the receipt. Failed integrity checks are exceptions and leave any
partial output for inspection; an output without its final manifest is not an
accepted dataset.

Fourteen focused tests cover integrity, cofilers, unknown metadata, missing
acceptance, native/strict disagreement, output refusal, Parquet determinism and
microsecond boundaries. Synthetic contract tests substitute native view results;
they are separate from the actual five-header native acceptance above. All 250
repository tests and existing structural validators passed at the worker base.
Central evidence registration belongs to the coordinator.

A new machine must supply its own accepted acquisition and matching receipt
hash; historical receipts do not establish that host's access or runtime
acceptance. A different input or bridge revision produces new anchors, which
must be reviewed and passed explicitly to the next stage.
