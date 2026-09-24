# Data lake: governed historical backfill (source layer)

`backfill.py` fills the lake's raw source layer from Alpaca's historical REST API under a shared token bucket
(`--rate`, at most 6,000 requests/min so the live monitor, scans and the engine keep headroom under the account's
10,000/min data limit, measured 2026-09-24), with HTTP 429 back-off to the limit's reset, one task per calendar day,
atomic owner-only day files (`<dataset>/<YYYY>/<MM>/<DD>.jsonl.gz`, gzip with a fixed mtime) and an append-only
`manifest.jsonl` (records, pages, sha256, bytes, fetch time). A day already in the manifest is skipped, so a run
resumes; a torn manifest line re-fetches that day. GET only; the data stays private (licensed market data and news).

## Datasets

| Dataset | Endpoint | Status |
| --- | --- | --- |
| `news` | `/v1beta1/news` (Benzinga via Alpaca), `include_content=true`, 50 per page, ascending | Backfilled 2015-01-01..2026-09-23 on 2026-09-24: 4,284 days, 2,213,433 articles, 46,568 requests, 0 HTTP 429, 0 failed days, 947 s at `--rate 3000 --workers 8` (private; about 1.1 GB) |

Minute bars, auctions, corporate actions and options follow the 2026-09-24 data-and-execution convergence record
(backlog items 7-11): page-level raw capture with a scope fingerprint that refuses to resume under a changed scope,
then a normalized Zstd Parquet layer read by DuckDB and the NautilusTrader catalog.

## Limits

- Records are re-serialized (sorted keys) per day, not stored as wire pages; the manifest does not yet carry the code
  sha or request parameters (a run header is written beside it by the operator).
- News `updated_at` changes after publication are not re-fetched; the live monitor records receive times going forward.

## Checks

`python3 -m unittest tests.test_data_lake_backfill` (synthetic opener and clock: paging, 429 back-off, resume, torn
manifest, rate cap).
