# Security identity and observation readiness

This wave checks a narrow prerequisite for historical mover research: what a
symbol means in a query, and when the returned information became available to
this runtime. The [frozen plan](plan.json) covers FB's rename to META across three
trading sessions in June 2022, four explicit symbol/asof cases and one current
META asset lookup. The [native receipt](native-receipt.json) records the executed
commands, original failure, correction, source hashes and offline replay.

The [previous native capture](../authenticated-data/README.md) established a small
AAPL bar/corporate-action sample. It did not establish a historically eligible
universe. This wave advances that boundary using the existing native Alpaca SDK
and DuckDB, without acquiring a broad dataset or adding a framework.

## Contract

Alpaca's [historical bars API](https://docs.alpaca.markets/us/reference/stockbars)
uses `asof` to identify the symbol's underlying entity; `-` disables mapping.
Returned historical bars can be relabeled to the requested symbol. Its
[market-data FAQ](https://docs.alpaca.markets/us/docs/market-data-faq) discusses
the FB/META example and later availability of mapping. That behavior is useful
for retrospective data retrieval but does not recreate what a strategy knew.

Meta's [company announcement](https://investor.atmeta.com/investor-news/press-release-details/2022/Meta-Platforms-Inc.-to-Change-Ticker-Symbol-to-META-on-June-9/default.aspx)
displays May 31, 2022, names June 9 as the ticker-change date and says the CUSIP
would remain unchanged. These are publisher-claimed historical facts. They do
not supply original observation or revision timestamps for today's API responses.

The native probe retains each case independently. Equal prices and date partitions
are reconciliation observations, not proof of a permanent security identity.
Today's asset UUID and tradability also cannot define historical universe membership.
Unknown valid-from, publication and revision timestamps remain unknown.

The local ledger preserves source observations, original timestamp text and exact
UTC nanoseconds. Conservative availability is the captured response time; neither
the historical event date nor the request's `asof` can replace it. Native DuckDB
selection must return no newly acquired rows at a 2022 decision cutoff. Boundary
queries show when these retrospective observations become locally available.
Historical strategy backtests need separately supported publication and revision
history. The [earlier temporal contract](../point-in-time/README.md) can represent
that availability basis; this capture supplies observed-time evidence only.

## Research and continuation

The first native acquisition returned seven HTTP200 responses. Its strict
normalizer rejected the META-unmapped case after observing a row with reported
zero volume, trade count and VWAP; the page also had a continuation token. The
original failed receipt remains immutable. The reviewed quality adapter fetched
only the saved continuation: one additional HTTP200 response completed the chain.
All four queries are now complete within the original cap. Source zeros remain
unchanged, with local quarantine separate from observation availability.

Alpaca's [stock aggregation description](https://docs.alpaca.markets/us/docs/market-data-faq#how-are-bars-aggregated)
says emitted stock bars have nonzero OHLC and volume. The observed zero-volume
row differs from that documented rule; its cause remains unknown. The FAQ's
zero-volume quote-midpoint explanation belongs to crypto and is not applied here.

One worker builds the bounded native probe and ledger, another examines selected
upstream identity/universe semantics, and an independent reviewer checks both.
The coordinator performs authenticated read-only requests and integrates native
results, catalog decisions, dashboard state and portable recipes.

The previous full public-star refresh remains dated September 20 at00:55UTC:
342 identities and no delta. This wave deepens selected source review; it does
not repeat that scan or claim a fresh exhaustive SOTA census. The next gate is a
permitted historical universe with inactive/delisted coverage and source revisions,
before chronological catalyst strategy evaluation. Paper orders remain deferred.

## Direct native results

The [adapter guide](../security-identity/README.md) explains the exact fixed
requests and portable commands. These project-owned adapters call native
Alpaca-py GET transport and DuckDB SQL/Parquet; they are not new upstream CLI
commands. The receipt includes every executed command with immutable hashes.

| Executed stage | Exit | Recorded result |
|---|---:|---|
| Original capture / original verify | 1 / 1 | Seven HTTP200 responses; strict numeric policy rejected the META-unmapped prefix |
| Native saved-token continuation | 0 | One new HTTP200; all four stock query chains terminal; eight HTTP attempts total |
| Offline quality verification | 0 | Identical anchored assessment; network disabled by Bubblewrap |
| Native DuckDB materialization | 0 | Ten query observations and one separate current asset snapshot; nine qualified and one quarantined |
| Historical cutoff and one nanosecond before first observation | 0 / 0 | Zero selected observations in both queries |
| Exact first observation boundary | 0 | Two qualified META-mapped observations |
| Latest META-unmapped observation boundary | 0 | Three observations: two qualified, one quarantined |

Mapped META/FB values agree on all seven raw fields across all three sessions.
The unmapped cases overlap on one date. Comparing each unmapped observation
separately gives three matches and one mismatch in all seven fields; the mismatch
is quarantined. This is not a clean, non-overlapping ticker partition and no rows
are merged or silently removed. Ten query observations do not mean ten independent
market sessions or securities.

The native all-case ledger proof returns 0 at the historical cutoff, 0 one
nanosecond before the first observation, 2 at that boundary, and 10 at the last
observation. Historical replay again returns 0 with the same selection hash.
Original and derived receipt anchors are separate, and each source page retains
its own observation time. Pagination completion does not prove an atomic
provider revision snapshot.

The final local SDK suite passed 310 tests without skips; independent focused
review passed 18. Cloud CI runs structural and dependency-light checks, with
optional native SDK cases reported as skips. Neither suite replays external
market-data acquisition in CI. No new model turn or net token-savings experiment
was performed in this wave.

## Next bounded convergence gate

The [502-identity grand index](../../../catalogs/us-equities/decision-index.json)
joins 342 identities from the dated public-star snapshot and 160 beyond it.
The [six selected source reviews](../../../catalogs/us-equities/security-identity-review.md)
cover Alpaca, LEAN, Zipline-reloaded, Qlib, NautilusTrader and the conditional
WRDS access bridge. WRDS/CRSP access is not installed, licensed or accepted here.

Next, establish a permitted historical security/universe source and an explicit
publication/revision availability basis. Freeze a small sample including an
inactive or delisted security before broad mover selection. Keep positive and
negative cases, query namespaces, split/dividend units and unavailable fields
visible. Only then advance the catalyst/mover factor dataset and chronological
strategy comparisons. Catalog breadth is not evidence that these data gates are
closed, that a strategy works, or that every future host is configured.
