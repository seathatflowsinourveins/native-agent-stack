# Bounded Alpaca historical acquisition

This bridge acquires a small retrospective AAPL sample through the installed
`alpaca-py==0.44.0` transport. The [plan](plan.json) is fixed before acquisition
and normalization. The sample matches the existing [LEAN action probe](../corporate-action-readiness/README.md):
25 exchange sessions from August 3 through September 4, 2020. It measures request
completion, source integrity and sample coverage. It calculates no returns,
positions, trading signals or performance statistics.

## Frozen request contract

| Field | Selection |
|---|---|
| Stock endpoint | `GET https://data.alpaca.markets/v2/stocks/bars` |
| Symbol / mapping date | `AAPL`, `asof=2020-09-04` |
| Bars | `1Day`, `sip`, `raw`, `USD`, ascending |
| Local UTC interval | `[2020-08-03T00:00:00Z, 2020-09-05T00:00:00Z)` |
| Inclusive wire end | `2020-09-04T23:59:59.999999999Z` |
| Pagination | 10 bars per page; at most 10 pages; terminal null token required |
| Corporate actions | `GET https://data.alpaca.markets/v1/corporate-actions` |
| Action filters | `AAPL`, cash dividends and forward splits, `region=us`, `data_quality=all` |
| Action process dates | Inclusive `2020-08-03` through `2020-09-04` |
| Action pagination | 1 action per page; at most 10 pages; terminal null token required |

Alpaca's [stock REST documentation](https://docs.alpaca.markets/us/reference/stockbars)
defines both bounds as inclusive. The wire end is therefore exactly one
nanosecond before the local exclusive bound. The explicit `asof` date identifies
the entity associated with a symbol; it does not establish when historical
information was available. `sip` and `raw` are explicit selections, not inferred
from the response or a subscription name. Daily timestamps must be New York
midnight, and their exchange dates must match the plan's exact 25 dates.
An empty final page is acceptable only after all expected sessions have appeared.
A short page never proves completion while a continuation token exists.

The current [corporate-action REST contract](https://docs.alpaca.markets/us/reference/corporateactions-1)
filters and sorts by process date. Event/ex dates and first local observation are
separate fields. `data_quality=all` also requests early incomplete records;
`complete` can exclude some of them. The service does not guarantee prompt
creation or availability after announcement. Missing ex dates, rates or security
identifiers are retained as incomplete metadata and excluded from qualified
comparison targets. Malformed values, missing identity or an uncheckable process
date fail the action stage while preserving its raw evidence. An empty/refused
action result does not establish that an action did not occur. The two LEAN
event dates are comparison targets, not a required claim of Alpaca coverage.

## Upstream API and bridge boundary

The native APIs used for authenticated HTTP are:

```python
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.historical.corporate_actions import CorporateActionsClient

# Credentials are supplied locally through the process environment.
# Each client's inherited RESTClient.get(path, data=query) sends one page.
```

The [SDK stock convenience method](https://alpaca.markets/sdks/python/api_reference/data/stock/historical.html)
and [corporate-action method](https://alpaca.markets/sdks/python/api_reference/data/corporate_actions/historical.html)
merge paginated results. Installed source inspection confirms that their `limit`
acts as a total retrieval cap and that merged results discard continuation
tokens. This bridge therefore uses the inherited native single-page `get`,
adds its own bounded pagination, and records every transition. It does not
claim to be an upstream pagination feature. The installed action request model
lacks `region` and `data_quality`, so the bridge sends those documented REST
parameters directly. No dependency upgrade is required.

Exact response preservation needs a deliberately pinned private seam:
`client._session` supplies a Requests response hook and `client._retry=0`
disables automatic retries. In 0.44.0, passing zero to the retry constructor
does not disable its default retries. The hook streams decoded HTTP entity
bytes in 64 KiB chunks, retaining at most 8 MiB. Oversized/interrupted bodies
are stored as prefixes with `body_complete=false` and cannot pass validation.
Complete bytes populate Requests' consumed-body cache before the upstream SDK
inspects JSON. These are entity bytes after HTTP content decoding, not a packet
capture or a signed provider attestation. Normalization independently parses
the retained bytes using `Decimal`, never the SDK's parsed floats/models.

Only the two fixed HTTPS endpoints and GET are accepted. Redirects and retries
are disabled, so each page has at most one HTTP attempt. Connect/read timeouts
are 10/30 seconds; the read timeout is an inactivity timeout, not a total run
deadline. Environment proxy and `.netrc` handling is disabled on these clients;
the recipe uses direct HTTPS with explicitly supplied SDK credentials. The
actual prepared method and URL are retained and checked against the intended
query; HTTP headers and exception text are never retained.

## Private acquisition and verification

Reuse the already adopted SDK interpreter. Supply credentials only to the
local process as `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY` through the existing
private account setup. Do not put secrets in commands, transcripts, fixtures or
receipts. This script does not inspect authentication stores or perform account
discovery. Its only remote operations are the bounded market-data GETs above.

```bash
SDK_PYTHON=/path/to/adopted/sdk/bin/python
ALPACA_RUN=/path/to/private/alpaca-historical/new-run
"$SDK_PYTHON" blueprints/us-equities/alpaca-historical/collect.py collect \
  --out "$ALPACA_RUN"
"$SDK_PYTHON" blueprints/us-equities/alpaca-historical/collect.py verify \
  --run "$ALPACA_RUN" --receipt-sha256 "$ALPACA_RECEIPT_SHA256"
```

Set `ALPACA_RECEIPT_SHA256` to the externally retained hash printed by the first
command. Verification never reacquires data. A new output directory outside
Git is mandatory. Files are exclusive-created with mode 0600; the leaf directory
uses 0700. Symlinks, parent traversal and overwrites are refused. The freeze binds
plan/collector bytes and installed SDK source/version identity before client
construction. Each body and page metadata file is saved before interpretation;
a final receipt binds their exact bytes and the recomputed normalized view.
Unexpected artifacts, changed source bytes, altered assessment values and wrong
external anchors fail verification. Interrupted runs retain their freeze and
completed page artifacts but have no accepted final receipt.

Both stages are attempted independently. A bars failure yields exit 1; bars
success yields exit 0 even if actions failed. Always inspect both stage statuses.
Action refusal/error bodies remain private. The JSON printed by either command
contains statuses, counts, session dates and a receipt hash, never normalized
price rows, action identifiers or private paths. Only this bounded summary may
be considered for a public receipt after review.

The Python `verify(run, expected_receipt_sha256)` function returns verified
`bars` and `actions` assessments. Complete assessments contain `rows`; failed
assessments have a reason and no accepted rows. Bars retain original timestamp,
integer nanoseconds, exchange date, exact decimal OHLCV/count/VWAP text and raw
source hash/size/first-observation anchors. Actions retain provider UUID,
process/ex/other dates, exact rate text, missing-field qualification and the
same source anchors. Unknown raw fields remain in the source body. Revisions
must use a new acquisition directory; no earlier source is overwritten.

## Verification and limits

```bash
"$SDK_PYTHON" -m unittest tests.test_alpaca_historical -v
python3 scripts/validate.py
python3 scripts/validate_catalogs.py
"$SDK_PYTHON" -m unittest discover -s tests -v
git diff --check
```

The offline suite uses synthetic HTTP bodies. It checks bounds, exact numbers
and nanoseconds, ordered/unique identities, token chains and caps, malformed
fields, incomplete actions, source tampering, external anchors, overwrite and
symlink refusal. A fake Requests adapter exercises the actual installed native
SDK GET and response-hook path, including the nine-digit end, action filters,
429 without retry, 302 without redirect and an oversized response. This is
transport compatibility evidence, not authenticated provider acceptance.

Complete pagination establishes a bounded query result, not a complete
historical market/action archive. These current retrospective observations do
not establish original first availability, an as-known universe, delisted-name
coverage or extreme-mover coverage. LEAN and Alpaca may disagree because their
sources and aggregation conventions differ; a later comparison must retain
every mismatch instead of imposing price equality. The existing 2021 control
segment remains previously inspected.
