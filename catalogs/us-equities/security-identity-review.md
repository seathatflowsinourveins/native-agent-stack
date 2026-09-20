# Security identity and revision readiness

This review keeps the selected Alpaca-py → DuckDB → LEAN path and narrows the next
acceptance to a three-session FB/META rename probe. Historical candidate-universe
coverage is still a data gate. Adding an engine does not supply missing listings,
delistings, revisions or original information availability.

The [machine-readable review](security-identity-review.json) records six decisions:
five existing identities and one conditional WRDS reference. It covers selected
sections of eight source files, six licenses and primary documentation at pinned
commits. This is deeper identity-contract review, not a fresh audit of all stars.
The last [complete identity refresh](../../blueprints/us-equities/authenticated-data/public-stars-refresh.json)
recorded 342 stars at 2026-09-20 00:55:35 UTC; no new pagination was performed here.
The earlier [six-alternative data review](authenticated-data-review.md) remains
applicable, including Massive, Databento and their availability limits.

## What the next native probe can establish

The coordinator froze June 8, 9 and 10, 2022, with daily SIP raw bars, ascending
order, page limit two and at most three pages per case. Expected outcomes below
are acceptance expectations, **not results produced by this source-review task**.

| Query ticker | Explicit `asof` | Expected sessions | Meaning |
| --- | --- | ---: | --- |
| META | 2022-06-10 | 3 | Resolve the renamed security and relabel its earlier FB bars |
| FB | 2022-06-08 | 3 | Resolve the pre-rename entity and include later META bars under FB |
| META | `-` | 2 | Disable mapping; June 9–10 ticker rows |
| FB | `-` | 1 | Disable mapping; June 8 ticker row |

Compare timestamps and raw numeric rows across mapped cases, then reconcile each
symbol-only subset. Preserve every page and actual observation time; incomplete
pagination or unexpected rows remain findings. A separate single
`TradingClient.get_asset("META")` call captures current UUID/status/tradability.
It cannot establish UUID continuity across the rename or past tradability.

Alpaca's [bars contract](https://docs.alpaca.markets/us/reference/stockbars) treats
`asof` as entity selection for a ticker, not a vendor-publication cutoff.
`-` disables mapping; an unrecognized ticker on the supplied date also falls back
to symbol-only behavior. The [FAQ](https://docs.alpaca.markets/us/docs/market-data-faq)
says the FB/META mapping became available June 10, the day after the rename.
A present-day successful reconstruction therefore cannot prove what a June 9
strategy could have obtained.

Meta's [company announcement](https://investor.atmeta.com/investor-news/press-release-details/2022/Meta-Platforms-Inc.-to-Change-Ticker-Symbol-to-META-on-June-9/default.aspx)
displays May 31, 2022 and identifies June 9 before market open as the effective
change. These are publisher-claimed historical dates, separate from our current
source review and unknown original API/local observation times.

## Keep four temporal facts separate

| Fact | Required representation | Insufficient substitute |
| --- | --- | --- |
| Security identity | Provider-scoped permanent security ID; company ID separately | Current ticker or issuer name |
| Symbol validity | Explicit interval linking ticker and security | One current asset record |
| Vendor revision | Dataset vintage and record revision/availability evidence | An economic event date or query `asof` |
| Local observation | Actual receipt time and raw-object hash | Backdating today's fetch to a historical session |

The [current Assets API](https://docs.alpaca.markets/us/reference/get-v2-assets-1)
documents all statuses by default and status/class/exchange/attribute filters,
not a historical asset-universe `asof`. Current inactive records are useful, but
do not establish that every historical delisted security is present.

## Focused selection

Full commit, license and source-byte hashes are in the JSON.

| Repository / reviewed pin | Decision and useful contract | Remaining boundary |
| --- | --- | --- |
| [Alpaca-py](https://github.com/alpacahq/alpaca-py/tree/232179c19091fd0f70daf0972a90bf8def329ec0), Apache-2.0 | Retain selected acquisition; separate current assets from bars mapping | Source HEAD is not an SDK upgrade; adopted 0.44.0 and actual REST drift remain separate |
| [Zipline-reloaded](https://github.com/stefan-jansen/zipline-reloaded/blob/943010b9da848e317fc520de87edade2b884d329/src/zipline/assets/assets.py), Apache-2.0 | Conditional reference: dated ticker ownership, ambiguous reuse errors and lifetime masks | Correctness depends on the ingested asset database; it is not a historical security-data subscription |
| [Qlib](https://github.com/microsoft/qlib/blob/be725493eb1a6bbb42bf11b37aa7669f59610ff1/qlib/data/data.py), MIT | Conditional research reference: retain membership spans with `as_list=False` | `as_list=True` gives an interval-wide union, not daily membership; PIT factors do not establish PIT universe coverage |
| [Nautilus Trader](https://github.com/nautechsystems/nautilus_trader/tree/519ed08313894a846a7015dd651963384d29d481), LGPL-3.0 | Retain runtime candidate; explicit symbol/venue ID and event/init fields | No automatic rename continuity; initialization time is not guaranteed vendor publication time; develop Rust layout is not installed release parity |
| [LEAN](https://github.com/QuantConnect/Lean/blob/985ef30ad3ac774218c5ac516b4cb0aa2655730f/Common/Data/Auxiliary/MapFile.cs), Apache-2.0 | Retain selected simulator and supplied map semantics | Empty maps return `HasData=true`; sentinel endpoints and this method alone cannot establish real coverage or observed delisting |
| [WRDS](https://github.com/wharton/wrds/tree/5d7bf38de5bd367852b7ccdd05079c1a1820f888), BSD-3-Clause | One new conditional reference: access bridge to licensed CRSP identity/delisting benchmarks | No account, subscription, data entitlement, install or authenticated query established |

Zipline's `include_start_date=False` provides an explicit first-session boundary:
a daily close is not available that morning. Qlib's instrument spans and LEAN's
map bounds require their own source provenance. Nautilus' reviewed
[Equity fields](https://github.com/nautechsystems/nautilus_trader/blob/519ed08313894a846a7015dd651963384d29d481/crates/model/src/instruments/equity.rs)
have optional ISIN and supplied event/init times; its
[InstrumentId](https://github.com/nautechsystems/nautilus_trader/blob/519ed08313894a846a7015dd651963384d29d481/crates/model/src/identifiers/instrument_id.rs)
is a symbol/venue pair. Those are useful runtime representations, not evidence
of a complete historical security master.

Two historical Nautilus Cython paths returned 404 at the pinned develop commit.
The review followed the current Rust paths at that same commit and records the
discovery misses. No installation or migration was attempted.

## Why WRDS remains conditional

[CRSP's provider documentation](https://indexes.morningstar.com/research-data-products)
describes permanent security identity and licensed research access. Its
[metadata](https://www.crsp.org/wp-content/uploads/appendix/FlagType_CL.html)
distinguishes security PERMNO from company PERMCO.
The [legacy WRDS demo documentation](https://wrds-www.wharton.upenn.edu/demo/crsp/form/)
shows identity histories and delisting fields, including missing-outcome codes.
The demo was read as documentation; no query was submitted.

WRDS [documents the SIZ-to-CIZ transition](https://wrds-www.wharton.upenn.edu/pages/data-announcements/changes-to-crsp-data/):
December 2024 data, released in February 2025, was the last legacy-format release.
Current entitled schema, definitions and vintage must be inspected before any
query. Do not transplant old table names or delisting-return formulas into CIZ,
and do not silently replace an unknown delisting outcome with zero.

The open client license supplies no CRSP use or redistribution rights. Even an
entitled current dataset does not establish what a historical strategy observed.
The immediate Alpaca probe can advance without acquiring this optional service.

## Native API shapes and next acceptance

These calls are **prospective**, using already constructed clients/providers.
They were reviewed against pinned upstream source and were not executed here.
Operator-supplied variables identify approved local fixtures or entitled data;
none initializes authentication or downloads a dataset.

```python
# Current state only; historical mapping uses the separate frozen data plan.
asset = trading_client.get_asset(symbol_or_asset_id="META")

# Optional synthetic identity oracle with a prepared Zipline asset database.
asset = finder.lookup_symbol(
    "SYNTH", as_of_date=decision_date, fuzzy=False, country_code="US"
)
mask = finder.lifetimes(
    dates=sessions, include_start_date=False, country_codes=["US"]
)

# Optional already initialized Qlib provider: retain validity spans.
spans = D.list_instruments(
    D.instruments(market=LOCAL_MARKET),
    start_time=START_DATE, end_time=END_DATE, freq="day", as_list=False
)

# Conditional WRDS connection only after separately confirmed entitlement.
tables = db.list_tables(library=ENTITLED_SCHEMA)
columns = db.describe_table(library=ENTITLED_SCHEMA, table=APPROVED_TABLE)
rows = db.raw_sql(
    approved_bounded_sql,
    params=identity_and_date_parameters,
    coerce_float=False,
    chunksize=1000,
)
```

The shown high-level Alpaca API is not the coordinator's paginated acquisition
implementation. WRDS SQL must itself bound the approved symbols and dates;
chunk size controls memory, not total result size. Table identifiers come from
reviewed schema discovery, while values use query parameters.

The next sequence is:

1. Complete and independently review the frozen rename acceptance, preserving
   unsupported behavior, incomplete pages and unknown historical availability.
2. Define a small historical-universe contract covering ticker reuse, listing
   and delisting intervals, source revisions, unknown outcomes and permitted use.
   Keep current broker tradability separate from research eligibility.
3. Add a conditional data source only for a demonstrated missing field or
   coverage requirement. Existing Massive/Databento decisions and licensed
   WRDS/CRSP remain options; no additional engine is required for this probe.

Prior [corporate-action evidence](../../blueprints/us-equities/corporate-action-readiness/README.md)
remains a bounded direct LEAN API result, with its upstream NUnit host unresolved.
This review makes no new strategy, profitability, +200% mover-universe, installed
runtime or universal-SOTA claim.
