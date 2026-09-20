# Authenticated historical data convergence

This wave advances the selected research stack from local sample mechanics to a
bounded authenticated Alpaca historical-data acquisition. The [frozen plan](plan.json)
defines AAPL daily SIP/raw/USD bars for August 3 through September 4, 2020,
explicit symbol-asof and complete bounded pagination. It also requests corporate
actions with the current REST quality fields, which the installed request model
does not expose. The [native receipt](native-receipt.json) records the successful
acquisition separately from the [six-alternative source review](../../../catalogs/us-equities/authenticated-data-review.md).

## Direct results

The September 20 run used installed Alpaca-py 0.44.0 and made five authenticated
GET requests. All returned HTTP 200. No additional login, SDK upgrade or data
purchase was needed for this sample.

| Native operation | Observed result |
| --- | --- |
| Historical bars, explicit SIP/raw/USD | 25 AAPL daily bars across 3 pages; terminal pagination |
| Corporate actions, US / `data_quality=all` | 2 qualified records across 2 pages; terminal pagination |
| Private integrity verification | Frozen plan, collector, SDK source fingerprints, raw bodies, prepared requests, metadata and receipt verified |
| Raw-close comparison to frozen LEAN output | 25/25 equal; no missing/extra sessions; maximum absolute difference `0.00` |
| Corporate-action reconciliation | Both numeric values equal; split ratio accepted; dividend currency absent, so cash-unit reconciliation remains open |
| Public-star refresh | 342 identities, no delta; combined catalog 501 identities / 1,024 typed pointers |

The sample contains historical values observed by this runtime in September 2026.
It does not reconstruct what a strategy knew in August 2020. The corporate-action
comparison treats missing currency as unknown, rather than a conflicting amount
or an inferred USD label. Raw provider payloads and credentials stay private.

Use the [native acquisition recipe](../alpaca-historical/README.md) to create a new
private run on a configured host. `collect.py` calls the upstream clients' GET
transport; pagination, precision and provenance checks are this repository's
small adapter. The pinned `_session` and `_retry` seams are explicit in that guide.

```sh
"$SDK_PYTHON" blueprints/us-equities/alpaca-historical/collect.py collect \
  --out "$NEW_PRIVATE_RUN"
"$SDK_PYTHON" blueprints/us-equities/alpaca-historical/collect.py verify \
  --run "$PRIVATE_RUN" --receipt-sha256 "$RECEIPT_SHA256"
python3 blueprints/us-equities/authenticated-data/compare.py \
  --run "$PRIVATE_RUN" --receipt-sha256 "$RECEIPT_SHA256" \
  --lean "$LEAN_NATIVE_RESULTS" --lean-sha256 "$LEAN_RESULTS_SHA256"
```

All three commands exited 0 for the retained sample. Read stage statuses even
when the acquisition exits 0: it indicates accepted bars, not guaranteed action
coverage. The authoring run's private receipt hash is
`a59c6ed74e839ca43ee704033e207865ed938a22e4738afce22ec197e91b6bcd`;
the LEAN reference hash is
`b31c282c90367c3baf87232772fc78a7bc36a8c64229faa2ef86a9068e88b25b`.
Use a new run's actual receipt hash on another host. No raw prices are published.

The full local SDK suite passed **292 tests with no skips**. Independent review
reproduced the native comparison and checked all 14 retained artifact anchors and
four installed SDK source hashes. Repository/catalog checks and the redacted
secret scan passed. The live Grafana dashboard rendered the new sample status;
this is recorded research progress, not continuous broker observation. GitHub
Actions validates each published commit without acquiring data or invoking models.

The first configured paper profile previously passed a native read-only account
request. Account authentication alone does not establish market-data coverage,
margin entitlement, account emptiness or broker execution. Credential values,
account identity and raw provider payloads stay outside this repository.

## Why this is the next step

The [previous catalyst dataset](../catalyst-dataset/README.md) preserved source
observations and missing headers. The [LEAN factor/map probe](../corporate-action-readiness/README.md)
established adjustment mechanics on 25 retained AAPL sessions. This wave checks
an independent provider sample against that narrow reference, retaining every
difference. Neither source is assumed to be a historically known security universe.

Alpaca documents inclusive start and end bounds. The local dataset instead uses
an explicit half-open interval; the request translates its end to the preceding
nanosecond. `asof` identifies the entity associated with a symbol, not when the
provider or this runtime first knew a fact. Follow every `next_page_token`, since
one response may be shorter than the requested page size even when more data
exists. See the [official historical-bars contract](https://docs.alpaca.markets/us/reference/stockbars).

Corporate-action `data_quality=all` includes incomplete early records, while the
default excludes some of them. A response still cannot guarantee immediate
availability after announcement, and process-date filtering differs from event
dates. Empty or refused responses must remain visible. See the [official
corporate-action contract](https://docs.alpaca.markets/us/reference/corporateactions-1).

## Catalog convergence

The [public identity refresh](public-stars-refresh.json) again returned 342 stars
with no added, removed or renamed identity pairs. The selected source challenge
examines corporate-action revisions, historical identity, storage versions and
validation. This is a dated selection across known responsibilities; it does not
claim a universal final SOTA census or that every catalogued repository is installed.

The existing Alpaca-py, EdgarTools, DuckDB and LEAN components remain the immediate
data path. Alternatives must supply a specific missing capability and their own
data rights, compatibility and native acceptance. A newer repository, a current
symbol list or a versioned store cannot recreate original historical observation.

## Roles and continuation

One worker implements the bounded native transport/provenance adapter, one reviews
selected upstream alternatives, and an independent reviewer inspects integrity,
precision, pagination and evidence. The coordinator alone performs authenticated
acquisition, integrates results, updates the dashboard and publishes verified files.

## Coverage and the next acceptance sequence

All requested ecosystem layers have catalog coverage. Installation and execution
remain capability-specific, with these operational gaps:

| Layer | Evidence and next requirement |
| --- | --- |
| Token efficiency | [Native context/usage evidence](../../../observability/session-e2e.md); matched whole-task provider savings remain unmeasured |
| Memory and RAG | [Memory lifecycle](../memory-lifecycle/README.md) and [retrieval evaluation](../retrieval-evaluation/README.md); improve held-out relevance before claiming compounding learning |
| Codex and Claude workers | [Native paired execution](../../../adoption/paired/README.md); provider cancellation and interrupted recovery remain pending |
| OmniRoute and DeerFlow | [Routing/orchestration catalog](../../../catalogs/us-equities/agents-operations.md); tool/context parity remains conditional; DeerFlow ACP workspace-write mapping is not a strict read-only worker policy |
| Hosting, macOS and WSL | [Adoption scope](../../../adoption/README.md); Linux/WSL same-host fresh-prefix acceptance does not establish macOS, second-machine or off-host recovery |
| Trading foundation | [Current open gates](../../../catalogs/us-equities/convergence-review.json); historical identity, eligible universe, revision availability, strategy merit and order recovery remain separate |

Next, establish the permitted historical universe and revision policy, including
delisted securities and missing observations. Freeze catalyst eligibility and
chronological controls before measuring a strategy. Then evaluate execution
assumptions, worker recovery and matched token usage. The [adoption manifest](../../../adoption/manifest.json)
and [update protocol](../../../adoption/update.md) tell future sessions and hosts
which native recipes to reuse and which acceptance results must be earned locally.

Next steps depend on the actual receipt: establish permitted historical universe
and revision coverage, then define chronological catalyst-to-price research with
missing-data and execution assumptions. Historical simulation remains active.
No order submission, paper-account reset, paid service or live promotion belongs
to this wave. Provider tokens saved and strategy profitability are not measured.
