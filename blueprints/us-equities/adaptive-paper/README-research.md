# Dated shadow catalyst watchlist

`market_research.py` produces a usable local research artifact from bounded Alpaca
news and optional IEX snapshots. It has no order, account, position, execution,
SEC acquisition or model-inference endpoints. Every article, market-context row
and review-queue item carries `engine_eligible: false`. Its scores prioritize
reading; they do not predict returns or establish a profitable strategy.

## Native reuse

The module uses **alpaca-py 0.44.0**, reviewed at
[`cc4cb3b7ba50ae250e621983c2779047fb16bb28`](https://github.com/alpacahq/alpaca-py/tree/cc4cb3b7ba50ae250e621983c2779047fb16bb28).
It calls the existing `NewsClient.get_news(NewsRequest(...))` and
`StockHistoricalDataClient.get_stock_snapshot(StockSnapshotRequest(...,
feed=DataFeed.IEX))`. These native clients serialize requests and parse their
responses; the local adapter adds request bounds and explicit provenance.
The unchanged official
[`tests/live/test_data_rest.py::test_get_news`](https://github.com/alpacahq/alpaca-py/blob/cc4cb3b7ba50ae250e621983c2779047fb16bb28/tests/live/test_data_rest.py#L54)
is the selected native read-only acceptance example, using an explicit three-item
limit. Its execution is separate from this module's mocked integration checks.

The current [news REST contract](https://docs.alpaca.markets/us/reference/news-3)
uses `GET https://data.alpaca.markets/v1beta1/news`, orders by update time,
allows up to 50 records per page and supplies pagination tokens. Defaults can
reflect a 15-minute entitlement delay, so this module sets the window explicitly
and reports HTTP refusals instead of claiming unverified real-time access.
The reviewed SDK automatically paginates if the item limit is omitted and loses
the final cursor from its aggregated return. This module sets a limit of 1–50,
retains cursor-presence at the response boundary, and independently caps **two
news GETs plus one snapshot GET**. A full item limit with a remaining cursor is
`capped_more_available`; a request-cap failure remains an incomplete result.

The session only permits those two exact HTTPS GET paths. SDK retries are disabled
after construction; environment proxies and redirects are disabled; connect/read
timeouts are five seconds each. Responses retain only status, observation time
and allowed rate headers. Source text and provider error bodies are never
printed by the CLI. The caller supplies credentials explicitly. A runtime
version match is not an attestation of every installed SDK file's hash.

## Run and artifact

Use the existing isolated SDK runtime. For an authorized account-data read, select
the explicit private credential file and a new private output path:

```sh
python blueprints/us-equities/adaptive-paper/market_research.py \
  --env-file "$PAPER_ENV_FILE" --symbols SPY,QQQ,AAPL,MSFT \
  --lookback-hours 24 --max-items 50 --out "$PRIVATE_RESEARCH_OUTPUT"
```

`--no-snapshots` performs news collection alone. `--now` freezes an explicit UTC
request-window end; omitting it uses current UTC. The credential parser accepts
only literal `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY`, without executing a
shell file. It refuses a symlink input. Outputs use exclusive creation and mode
0600. The CLI prints only status, counts and an artifact digest. It does not
schedule recurring work or contact TypeSafe, Claude or the SEC.

The Python entry point is:

```python
collect(key, secret, symbols, *, now, lookback_hours=24,
        max_items=50, include_snapshots=True)
```

Each article retains provider-created publication time, updated time, observation
time **in this collection run**, a source hash and a stable revision ID. Provider
publication time is not independently verified. `available_at` is the maximum of
those three times; material fetched now cannot establish earlier availability.
Only the latest consistent revision of an article is displayed. Conflicting
content under one revision timestamp is quarantined, as are future updates,
invalid identities and records outside the explicit symbol universe. The adapter
does not infer symbols for global/unsymbolized news or claim exhaustive coverage.

Categories are transparent case-insensitive term matches for earnings, guidance,
regulatory, capital, merger and other. The score adds category review weight
(0–3) and publication-age bucket (0–3). A newly updated old article keeps its old
publication-age score. Such matches are leads for evidence review, not confirmed
event classifications. HTML becomes plain bounded text; embedded instructions
remain untrusted evidence and cannot change control flow.

IEX context reports last-trade change from the prior daily close, quote spread
and a partial-day/prior-full-day volume ratio when the source fields are valid.
Every component retains its own time. Stale or zero closed-session quotes are
flagged and do not erase usable news. The volume ratio is explicitly **not**
time-normalized relative volume or consolidated-market activity. News window
time and newly observed market context are separate; this is not a historical
price replay. No return attribution or pre-positioning claim is made.
Stock-price context requires at least $0.0001 and equity bar volumes must be
nonnegative integers. Absolute price changes above 10,000% or volume ratios above
1,000 are flagged for source review instead of displayed as ordinary ratios.
These are display-quality bounds, not claims that an extreme move is impossible:
valid component prices/volumes and the source hash remain in the limited context.

## Existing SEC and advisory layers to extend

The existing [SEC provenance adapter](../catalyst-provenance/catalyst.py) already
provides `acceptance_time`, `parse_header`, `eligible_at`, immutable source hashes
and `available_at = max(accepted_at, first_observed_at)`. Its acquisition is
deliberately frozen to a historical date; running it unchanged is not today's
scanner. The [dataset bridge](../catalyst-dataset/dataset.py) already has the
EdgarTools header/item taxonomy, DuckDB materialization and as-of filtering.
Extend those contracts rather than duplicate their timestamp or filing parsers.

The installed **EdgarTools 5.58.0**, reviewed at
[`abe44344c56cf4bfb5443e0debca7e39342f6e7a`](https://github.com/dgunning/edgartools/tree/abe44344c56cf4bfb5443e0debca7e39342f6e7a),
has `edgar.get_current_filings(form="8-K", page_size=40)` for a bounded current
page. Do not use `page_size=None`, which walks all pages. Source review of
`edgar/current_filings.py::get_current_entries_on_page` identifies a 503-as-empty
feed behavior; a future native acquisition must independently verify HTTP 200
before treating an empty page as fresh success. Preserve the existing private
declared SEC identity and two-requests/second policy. The [SEC FAQ](https://www.sec.gov/about/webmaster-frequently-asked-questions)
distinguishes acceptance from actual public availability and requires a declared
user agent; it provides no first-availability timestamp. An 8-K item code alone
is not a catalyst, sentiment, incentive or price label.

The installed TypeSafe skill and agent-lab `docs/typesafe-practice.md` were read
for this integration. Its existing `tools/ecosystem/typesafe-pilot` uses
Promptfoo 0.123.1 and `jev-1.13.0` for bounded source/claim support judgments.
Reuse its strict verdict/distribution checks, source hash and deterministic
availability gate when an authorized separately scoped advisory evaluation is
requested. That 16-case pilot does not qualify market-event classification or
grant another project's credential access. This module records
`not_executed_unqualified`; it never fabricates an inference result.

Live [TypeSafe Python guidance](https://docs.typesafe.ai/sdk/python/usage) supports
managed `AsyncTypeSafeClient`, batched independent questions and a typed
`SystemOneResponse`. The reviewed SDK source revision
[`2ce5c65f13646cab6e6f782328194c9d85f3300a`](https://github.com/typesafe-ai/typesafe-sdk-python/tree/2ce5c65f13646cab6e6f782328194c9d85f3300a)
declares version 0.7.0. It was source-reviewed here, not installed or executed.
The [citation-check cookbook](https://docs.typesafe.ai/cookbooks/citation_check)
fits source-support review; the [SEC classification cookbook](https://docs.typesafe.ai/cookbooks/classification_using_confidence)
demonstrates abstaining to a broader label. Their example confidence thresholds
are not trading acceptance thresholds. Keep any future judgments outside the
native strategy callback, cache by complete source revision/model/questions,
retain usage/failures, and qualify a separate chronological domain corpus.

## Verification boundary

```sh
python -m unittest discover -s tests -p test_adaptive_market_research.py -v
```

These local synthetic tests exercise native SDK serialization with mocked HTTP:
bounded pagination and rate failures, chronology, revisions, untrusted text,
source URLs, immutable review eligibility and closed-session market context.
They do not establish authenticated data entitlement, SEC freshness, model
accuracy, strategy quality or broker execution. Root/coordinator performs any
separately authorized native read and retains its actual receipt.
