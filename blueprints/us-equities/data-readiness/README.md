# Catalyst and historical-price readiness

This September 20 wave turns the accepted SEC acquisition into a queryable
metadata dataset and checks existing LEAN corporate-action semantics. The
[frozen plan](plan.json) records the scope and completion criteria. Historical
simulation remains active; dedicated Alpaca paper remains deferred.

## Accepted results

| Native path | Direct result | Remaining boundary |
| --- | --- | --- |
| [EdgarTools → DuckDB](../catalyst-dataset/README.md) | 371 memberships / 360 accessions; 5 verified headers; 9 item links; 366 unfetched rows preserved | Header declarations and present observation do not establish historical catalyst availability |
| [Native SQL availability](../catalyst-dataset/native-receipt.json) | Historical cutoff: 0; observation boundaries: 0 → 1 → 4 → 5; repeated Parquet and manifests byte-identical | No issuer-price or historically known security join |
| [LEAN factor/map probe](../corporate-action-readiness/README.md) | 25 AAPL sessions; dividend 0.82 USD per raw share; split factor 0.25 | Retrospective sample; no holdings, cash accounting or P&L |
| [Native LEAN test-host attempt](../corporate-action-readiness/receipt.json) | Exit 1, 0 upstream NUnit cases executed | Missing SGX fixture data and Python GIL failure remain unresolved |

The split basis comparison changes the same August 28 close from 499.23 to
124.8075 when using the September 4 basis. This is a normalization result, not a
loss, forecast or investment return. The probe also distinguishes one native
missing-basis rejection from one repository adapter cutoff rejection.

The linked recipes preserve exact executed commands and native API calls;
their CLI adapters are repository code around upstream SDKs. Independent review
checked 17 catalyst receipt artifacts and 84 corporate-action artifacts, plus
the source/parser/plan anchors and focused contract tests. Integrated repository
verification and publication are recorded in [verification.json](verification.json).

## Roles and native path

The catalyst worker combines the complementary native EdgarTools header views
with the existing strict provenance parser, then uses native DuckDB to create
typed Parquet tables and query availability. The price-data worker exercises
LEAN factor/map APIs on the existing AAPL sample. An independent reviewer checks
source integrity, missing-data behavior, temporal boundaries and the stated
limits. The coordinator integrates evidence, catalog decisions and dashboard
checkpoints before publication.

The SEC input scope is 371 issuer/accession memberships, including 360 unique
accessions. Only five headers were acquired; 366 remain unknown. Nine item
memberships are header declarations, not nine verified catalysts. These bytes
were observed in 2026 even though the SEC acceptance dates are in 2020.

The price scope is 25 existing AAPL daily sessions, August 3 through September 4,
2020. Native adjustment mechanics can be verified without treating a current
factor file as historical knowledge. Neither lane establishes a market-wide
extreme-mover universe, a profitable strategy or accepted paper execution.

## Current source decisions

The [selected source review](../../../catalogs/us-equities/data-readiness-review.json)
distinguishes current upstream HEADs from executed package pins. The
[public-star refresh](public-stars-refresh.json) returned 342 repositories and
zero added, removed or renamed identity pairs against the previous snapshot.
Unchanged identities do not imply unchanged source contents.

EdgarTools, DuckDB and LEAN already cover this bounded work. Alpaca-py remains the
preferred subsequent authenticated historical-data path; Massive and Databento
remain conditional alternatives with separate data rights and account gates.
No new general agent framework or data runtime is needed to satisfy this wave.

The [existing dashboard](../../../observability/grand-dashboard/README.md)
shows these two acceptances, the unresolved upstream suite and the current wave.
Its timestamp is a coordinator checkpoint, separate from emitter health and
native worker process liveness. Context tools and bounded evidence packets keep
raw data out of prompts; this wave does not measure causal net provider savings.

## Following acceptance

Select a small historical Alpaca SIP/RAW acquisition with explicit dates, symbol
`asof` and completed pagination when local credentials are ready. Alpaca Basic
documents history since 2016 and permits older SIP history; a paid real-time
subscription is not intrinsically required for that historical request. All
stock-data requests still need authentication. The installed corporate-action
request model lacks the current REST `region` and `data_quality` fields; resolve
that interface gap before making completeness claims. See the [official plan
and authentication documentation](https://docs.alpaca.markets/us/docs/about-market-data-api),
[historical SIP FAQ](https://docs.alpaca.markets/us/docs/market-data-faq), and
[corporate-action endpoint](https://docs.alpaca.markets/us/reference/corporateactions-1).

Keep historical issuer/security mappings, delistings, source revisions,
dissemination/receipt time and missing-data coverage as explicit gates. No login
is needed for this offline wave. Current-account entitlement, orders and live
promotion are not inferred from catalog membership or successful local tests.
