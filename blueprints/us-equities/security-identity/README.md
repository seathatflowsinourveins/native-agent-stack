# FB/META query identity and observation-time proof

The [frozen plan](plan.json) defines four small historical bar queries around the
June 2022 FB/META rename and one current META asset lookup. This is a retrospective
provider-query comparison and an observation eligibility test. It produces no
permanent security master, historical tradable universe, return labels or strategy.

## Fixed acquisition

All stock cases request `SIP`, raw prices, USD, `1Day`, ascending, over the local
half-open UTC window `[2022-06-08T00:00:00Z, 2022-06-11T00:00:00Z)`. The three
New York exchange dates are June 8, 9 and 10. Alpaca uses inclusive HTTP bounds,
so the exact wire end is `2022-06-10T23:59:59.999999999Z`.

| Case | Requested symbol | Explicit symbol asof |
|---|---|---|
| `meta_mapped` | META | 2022-06-10 |
| `fb_mapped` | FB | 2022-06-08 |
| `meta_unmapped` | META | `-` |
| `fb_unmapped` | FB | `-` |

The [stock endpoint documentation](https://docs.alpaca.markets/us/reference/stockbars)
defines `asof` as the date used to identify the entity associated with a symbol.
The special `-` value disables symbol mapping. It is not an information-availability
cutoff. Responses retain the requested case and returned symbol label. Matching
raw fields are comparison observations and cannot assign a permanent security ID.
Mapped aliases and the unmapped date partition are reported separately. Missing
dates and empty successful responses remain visible; the implementation does not
require the documentation example to match a newly observed provider result.

Every case uses page limit 2 and at most 3 pages. A terminal null continuation
token is required, regardless of page size. Duplicate timestamps, repeated tokens,
wrong symbols, out-of-window or unordered bars, malformed/nonfinite numbers and
altered actual wire parameters fail that case. Each case proceeds independently.

The fifth and final stage is exactly one native inherited
`TradingClient(paper=True, raw_data=True).get('/assets/META', data={})` call to
`https://paper-api.alpaca.markets/v2/assets/META`. It does not invoke the convenience
`get_asset` method, enumerate assets, follow a returned UUID or request FB. Its
UUID, symbol, status, exchange, asset class and tradable flag are current endpoint
observations. Historical valid-from/to, original publication and provider revision
times remain NULL. Tradable is not an account entitlement or a 2022 capability
claim. A 404 is a current lookup result, not evidence of a historical delisting.

`NativeIdentityPages` reuses the accepted [AAPL bridge](../alpaca-historical/README.md)
response hook, GET dispatch and close methods without modifying that bridge. Its
small initializer limits clients to these stock cases and the paper META endpoint.
Native SDK source fingerprints include the trading client. The original helper's
complete bytes are frozen alongside the new probe and plan. The pinned private SDK
session/retry and Requests consumed-body seams remain explicit compatibility
boundaries, not new upstream SDK features.

The maximum is 13 HTTP attempts: up to 12 stock pages and one asset lookup. Each
page has one attempt, no redirects or automatic retry, 10/30-second connect/read
timeouts and an 8 MiB decoded-body bound. Oversized/interrupted bodies retain only
their bounded prefix and are marked incomplete. The read timeout measures inactivity,
not total elapsed time. Native sign-in files are never opened; these isolated SDK
clients disable environment proxies and `.netrc` handling. Actual prepared URLs,
status and observation intervals are captured; credentials and HTTP headers are not.

## Private capture and offline verification

Use the adopted `alpaca-py==0.44.0` and `duckdb==1.5.5` environment. A local operator
supplies `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY` through the existing private
process setup. Do not write credentials in command history, transcripts or source.
Both output directories must be new, outside Git, and free of symlink/parent traversal.

```bash
SDK_PYTHON=/path/to/adopted/sdk/bin/python
IDENTITY_RUN=/path/to/private/identity/new-capture
IDENTITY_LEDGER=/path/to/private/identity/new-ledger
"$SDK_PYTHON" blueprints/us-equities/security-identity/probe.py collect \
  --out "$IDENTITY_RUN"
"$SDK_PYTHON" blueprints/us-equities/security-identity/probe.py verify \
  --run "$IDENTITY_RUN" --receipt-sha256 "$IDENTITY_RECEIPT_SHA256"
"$SDK_PYTHON" blueprints/us-equities/security-identity/ledger.py materialize \
  --source "$IDENTITY_RUN" --receipt-sha256 "$IDENTITY_RECEIPT_SHA256" \
  --out "$IDENTITY_LEDGER"
"$SDK_PYTHON" blueprints/us-equities/security-identity/ledger.py select \
  --ledger "$IDENTITY_LEDGER" --manifest-sha256 "$IDENTITY_LEDGER_SHA256" \
  --case-id meta_mapped --cutoff 2022-06-11T00:00:00Z
```

Retain each printed receipt/manifest hash outside the corresponding artifact and
set the next command's hash variable to that exact value. Capture is the only
command that can make a network request. The other commands reparse retained bytes.
Probe exit 0 means all four stock query chains completed, including possible empty
responses; always inspect the separate asset status. Failed stages retain their
response evidence and yield no accepted normalized rows. An interrupted capture
retains completed pages and the freeze but has no accepted final receipt.

Private source files and metadata are exclusive-created with mode 0600 in a 0700
leaf directory. The final receipt binds all raw bytes, intended and actual requests,
observation intervals, code and runtime identities. Verification requires the
external anchor, recomputes normalized values from exact Decimal JSON, and rejects
tampering, assessment mismatches, unexpected files or overwrite attempts. Raw
bar series, provider asset UUIDs and private paths stay outside public receipts.
Printed output contains only bounded statuses, counts, dates and integrity hashes.

## Native temporal ledger

Materialization copies the complete retained acquisition into a private source
subdirectory, revalidates it under the external anchor, and creates native DuckDB
`bars` and `assets` tables before writing Parquet. No synthetic-only validator from
the earlier point-in-time fixtures is applied to this real acquisition interface.

The separate time axes are:

| Field | Meaning |
|---|---|
| `request_asof` | Provider query's symbol-mapping date or `-` |
| `event_at` / `event_ns` | Historical bar start; exact source UTC text and BIGINT nanoseconds |
| `first_observed_at` / `observed_ns` | Completion of this retained local page observation |
| `available_ns` | Exactly `observed_ns`; never backdated to event time |
| Security valid-from/to | Unknown; historical bar time does not establish alias validity |
| Original publication / provider revision | Unknown |

Every bar also retains query case, requested/returned symbol, source hash/size and
acquisition receipt hash. Prices remain exact decimal text. The current asset
snapshot is stored separately and is absent from [eligibility SQL](select.sql).
It cannot make a historical universe member eligible.

All predicates use native signed BIGINT UTC nanoseconds. The proof queries the
historical cutoff, one nanosecond before the earliest accepted bar observation,
that exact boundary, the latest accepted bar observation, then the historical
cutoff again. Expected counts are derived from the acquired rows, not assumed
sample size. An all-empty acquisition has no accepted bar observation boundary.
The selection command requires one explicit case and returns count/hash metadata,
not raw prices.

This selects eligible observations; it does not select the latest semantic
revision. All query namespaces remain distinct. Conflicting semantic revisions
with the same case/event/observation instant are refused. No provider order is
invented from local array position. Hypothetical revision tests are explicitly
synthetic; actual provider revision-order and original-availability acceptance
remain unresolved.

The ledger manifest binds exact source, Parquet, new bridge, reused helper and SQL
bytes. Anchored selection checks the complete payload set and current pinned bridge/
SQL identity, stages verified bytes privately, replays source parsing, compares
every materialized row with that source view, and recomputes eligibility. Source
case/asset statuses remain in the ledger summary so an empty 200 and a failed
request stay distinguishable. An earlier ledger must be read with its matching
code/SQL revision; changing the current files does not silently reinterpret it.

## Checks

```bash
"$SDK_PYTHON" -m unittest tests.test_security_identity -v
python3 scripts/validate.py
python3 scripts/validate_catalogs.py
"$SDK_PYTHON" -m unittest discover -s tests -v
git diff --check
```

Offline tests use synthetic bodies and hypothetical revisions. The transport test
executes installed native SDK GETs through an in-memory Requests adapter, proving
all four asof/symbol combinations, the nine-digit end and exactly one paper asset
path without external access. Dependency availability is checked before importing
the optional SDK, so the lightweight CI environment can skip that native check.
Native authenticated counts belong in a separately reviewed execution receipt;
these tests do not establish provider acceptance.

## Retained zero-activity observation and bounded continuation

The original native capture returned HTTP 200 for every attempted request, but
the META-unmapped case failed the original positive-VWAP guard. Its first page
contained a positive-OHLC row reporting numeric `v=0`, `n=0`, `vw=0`, followed by
a row with positive activity fields. That page also had a non-null continuation
token. The failure stopped pagination; reparsing the page alone cannot establish
a complete query.

The [official stock aggregation FAQ](https://docs.alpaca.markets/us/docs/market-data-faq)
states that emitted stock bars require nonzero volume and OHLC. The retained
zero-volume observation conflicts with that documented rule. The cause remains
unknown. The FAQ's separate crypto midpoint explanation is not applied to this
stock observation. The installed native `Bar` model accepts zero numeric fields;
SDK schema acceptance neither explains the source discrepancy nor qualifies a
price for trading.

The new [quality adapter](quality.py) leaves the original probe and acquisition
receipt unchanged. It first verifies the original external receipt anchor, copies
all original artifacts to a new private directory and reproduces the original
failed status. It then reparses exact source numbers under a separately frozen
quality policy. All zero values remain zero; no replacement, imputation or
synthetic VWAP is introduced.

`reported_zero_activity=true` means exactly that volume, count and VWAP in this
source row are all numeric zeros. Its local quality is
`quarantined_reported_zero_activity` and `price_observation_qualified=false`.
Other zero combinations are also quarantined. Positive activity fields can qualify
an observation under this local numeric policy; this never establishes trade,
fill, halt, security identity or market-wide activity claims. Documentation
discrepancy counts remain separate and visible. Unknown historical validity and
original-availability fields remain NULL.

```bash
# Offline reparse of retained pages; an unfinished query remains partial.
"$SDK_PYTHON" blueprints/us-equities/security-identity/quality.py derive \
  --source "$IDENTITY_RUN" --receipt-sha256 "$IDENTITY_RECEIPT_SHA256" \
  --out "$QUALITY_DERIVATION"

# Explicitly authorized continuation in a different new directory.
"$SDK_PYTHON" blueprints/us-equities/security-identity/quality.py resume \
  --source "$IDENTITY_RUN" --receipt-sha256 "$IDENTITY_RECEIPT_SHA256" \
  --out "$QUALITY_RESUMED_RUN"

"$SDK_PYTHON" blueprints/us-equities/security-identity/quality.py verify \
  --run "$QUALITY_RESUMED_RUN" --receipt-sha256 "$QUALITY_RECEIPT_SHA256"
"$SDK_PYTHON" blueprints/us-equities/security-identity/ledger.py materialize \
  --derived --source "$QUALITY_RESUMED_RUN" \
  --receipt-sha256 "$QUALITY_RECEIPT_SHA256" --out "$QUALITY_LEDGER"
```

Only `resume` can issue new requests. It keeps all original pages, case results
and the current asset snapshot, then uses the saved META-unmapped token with
the original query parameters. It never re-fetches page 1 or another case/asset.
At most two additional one-attempt requests fit inside the original three-page
case limit and 13-attempt overall ceiling. Every new response has its own raw
bytes, status and observation instant. A refusal, malformed response or capped
nonterminal chain remains failed/partial and retains the already validated
prefix. No unchanged failure is retried. Offline derive/verify/materialize/select
perform no requests and never construct an authenticated client.

The new receipt binds original source/code hashes, the new quality policy and
adapter, and any continuation raw pages and metadata. Its public summary keeps
`original_probe_exit`, original case status and current normalization/query
completion separate. Mapped alias comparisons and every unmapped observation's
raw-field comparison remain separate; overlapping dates with conflicting values
are counted without merging or discarding either query observation.
Before a real continuation client is constructed, its current SDK version and
source fingerprints are frozen separately from the original capture's runtime.
Offline verification checks that retained identity without importing the SDK;
injected test transports are labeled explicitly and claim no native identity.

The derived ledger retains both original and derivation receipt anchors, source
phase and quality flags. Eligibility still means that an observation was received
by the cutoff. Results partition their count into `qualified_count` and
`quarantined_count`; quarantined records remain visible as observations and are
never silently promoted into prices for a trading or fill model. Original event
and observation nanoseconds are unchanged; only new continuation pages receive
new observation times. Ledger verification also binds the quality adapter bytes
and replays its anchored derivation before checking Parquet and SQL results.
Pages observed at different times do not establish an atomic provider snapshot
or provider revision ordering.
