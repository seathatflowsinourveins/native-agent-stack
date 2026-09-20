# Bounded lifecycle documents

This sample qualifies three documentary claims: Meta's FB→META rename, the
Roundhill ETF's earlier META→METV rename, and Twitter common stock's NYSE trading
suspension. It uses six fixed public documents and the existing EdgarTools and
DuckDB runtimes. It acquires no prices, broker assets, accounts or orders.

The [frozen plan](plan.json) permits one attempt per source, at most six attempts,
8 MiB per response, no redirects or cache reuse, and skips the remaining requests
to an origin after HTTP 401/403/429. The coordinator's
[capture adapter](../catalyst-convergence/capture_sources.py) preserves complete
or partial response bytes, status, exact prepared URL and nanosecond observation
times privately. Each response gets an immediate immutable metadata file. The
external manifest hash anchors the plan, pre-request transport freeze, six bodies
and six metadata files. A failed source remains a diagnostic entry.

## Two separate capabilities

The issuer documents support retrospective event claims and the ordering of the
two different uses of META. Their displayed publication dates remain historical
publisher claims, even though the documents were retrieved later. The SEC 8-K
supplies acceptance and filing-date text; the native parser returns a naive
acceptance value, so this adapter retains its text and leaves its zone and UTC
nanoseconds unknown. A filing date is not an acceptance instant.

The observation ledger answers when **this capture** had a supported documentary
claim. `available_ns = observed_ns` uses exact UTC BIGINT nanoseconds. The 2022
cutoff and its replay exclude documents observed in 2026. The proof also checks
one nanosecond before the earliest observation, its exact boundary and the latest
observation. Source publication dates never backdate local availability.

The project-assigned `documentary_security_scope` distinguishes company Class A
stock, fund shares and Twitter common stock. It is not a permanent security ID
or a cross-provider crosswalk. Event dates are date-level claims with the source's
timing language; they are not fabricated midnight timestamps or complete symbol
ownership intervals. The two rename claims can establish documentary ticker
reuse without claiming continuous ownership through the intervening months.
NYSE suspension and a Form 25 notification do not establish a legal delisting or
registration-termination instant. These fields, provider revisions and validity
intervals remain null. No query returns an eligible historical trading universe.

The accepted [FB/META observation receipt](../identity-readiness/native-receipt.json)
provides separate retrospective alias-query context, anchored in the plan by its
existing quality receipt hash. This ledger does not reingest its prices or join
the documentary scopes to provider IDs. The quarantined zero-activity observation
keeps its unknown origin; the Roundhill document does not resolve it.

## Native operations and the project bridge

`sample.py` is a small project adapter, not an upstream CLI. EdgarTools 5.58.0
executes `FilingSGML.from_text`, `get_document_by_sequence("1")` and
`HTMLParser().parse(...).to_markdown()` locally. It never constructs an entity or
filing downloader. The four installed source files are fingerprinted before
parsing. Fixed, manually reviewed text witnesses qualify only the three planned
claims; this is not a general event extractor or automatic revision resolver.
Missing witnesses or native parse failures leave claims unresolved.

The qualifier copies the exact capture and freezes its own code, shared helper,
plan and SQL. `verify --reparse` reproduces the native parse from retained bytes
under the same parser fingerprint. Plain `verify` uses the externally anchored
derived text and checks its deterministic claim construction without importing
EdgarTools, permitting the separate existing DuckDB runtime. DuckDB 1.5.5 writes
Parquet, executes the frozen SQL and verifies every materialized row against the
anchored claims. It queries a private copy of verified bytes. The qualified
receipt and ledger receipt are separate external trust anchors.

```sh
# Run these with networking denied. All output paths must be new and outside Git.
"$EDGAR_PYTHON" blueprints/us-equities/lifecycle-sample/sample.py qualify \
  --source "$CAPTURE" --receipt-sha256 "$CAPTURE_SHA" --out "$QUALIFIED"
"$EDGAR_PYTHON" blueprints/us-equities/lifecycle-sample/sample.py verify \
  --source "$QUALIFIED" --receipt-sha256 "$QUALIFIED_SHA" --reparse
"$SDK_PYTHON" blueprints/us-equities/lifecycle-sample/sample.py materialize \
  --source "$QUALIFIED" --receipt-sha256 "$QUALIFIED_SHA" --out "$LEDGER"
"$SDK_PYTHON" blueprints/us-equities/lifecycle-sample/sample.py verify-ledger \
  --source "$LEDGER" --receipt-sha256 "$LEDGER_SHA"
```

These commands print statuses, counts and hashes. CLI success means the operation
completed with integrity checks; inspect `supported_claims` and `source_statuses`
for source availability. Partial qualification is useful evidence and is not
silently promoted to complete source coverage. Public native execution results
belong to the coordinator's convergence receipt, separately from this code and
[source review](../../../catalogs/us-equities/lifecycle-source-review.md).

Focused checks are `python -m unittest tests.test_lifecycle_sample -v`. The
lightweight runtime skips the two optional native checks; each existing native
environment exercises its own integration without installing the other's
dependency. Fixtures are explicitly synthetic and contain no provider payloads.

## Recorded native result

The [September20 receipt](native-receipt.json) records six complete HTTP200 bodies,
three supported nonsynthetic documentary claims and native offline acceptance in
the adopted EdgarTools and DuckDB environments. Historical/before-first/first/last
observation selections are0/0/1/3; historical replay remains0. Independent reparse
and ledger verification reproduced the results and checked50 referenced file
hashes/sizes. Exact commands and all three external bundle anchors are in the receipt.
Historical universe eligibility, original revisions, permanent identity and legal
delisting instants remain unestablished.
