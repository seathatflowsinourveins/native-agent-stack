# Lifecycle source qualification

Three hand-selected cases advance the identity gate without adding a provider,
engine or historical-universe claim. The source contract, native document
extraction and actual acquisition receipts are separate evidence layers. The
[machine-readable review](lifecycle-source-review.json) records the decisions and
the [sample](../../blueprints/us-equities/lifecycle-sample/README.md) specifies the
bounded implementation.

| Case | Primary basis and supported claim | Remaining boundary |
| --- | --- | --- |
| Meta company Class A stock | [Issuer announcement](https://investor.atmeta.com/investor-news/press-release-details/2022/Meta-Platforms-Inc.-to-Change-Ticker-Symbol-to-META-on-June-9/default.aspx), displayed May 31, 2022: FB changes to META before the June 9 market open; class and CUSIP continuity are stated | CUSIP value/provider permanent-ID crosswalk, complete listing interval, original vendor availability and revisions are not supplied |
| Roundhill ETF shares | [Issuer-distributed release](https://www.prnewswire.com/news-releases/roundhill-ball-metaverse-etf-to-change-ticker-symbol-to-metv-301461328.html), displayed January 14, 2022 at 16:30 ET: META changes to METV at January 31 trading open | The fund and Meta stock remain separate documentary identities; this does not identify the origin of any anomalous provider bar |
| Twitter common stock on NYSE | [8-K Item 3.01](https://www.sec.gov/Archives/edgar/data/1418091/000119312522272772/d411753d8k.htm): trading was suspended before October 28, 2022 NYSE open following the merger | Suspension, requested delisting, Form 25 filing and legal registration termination are different facts; legal effective instant stays unknown |

The [OCC's January 21 notice](https://infomemo.theocc.com/infomemos?number=49960)
corroborates the Roundhill ticker change. Its options adjustment summary is a
corroborating public research source, outside the six-document native capture.
The distinct January and June announcements support retrospective ticker reuse.
They do not prove a complete historical ticker master or identify all securities
that ever used META.

Twitter's [8-K filing index](https://www.sec.gov/Archives/edgar/data/1418091/000119312522272772/0001193125-22-272772-index.htm)
displays October 31 as the filing date and October 28 at 20:22:36 as acceptance.
The [Form 25 index](https://www.sec.gov/Archives/edgar/data/1418091/000087666122000890/0000876661-22-000890-index.htm)
is a separate exchange submission. Its metadata is retained as stated, without
converting an index effectiveness date into a legal delisting instant. Native
naive acceptance text is retained without inventing a timezone conversion.

The installed upstream implementation is sufficient: EdgarTools 5.58.0 parses
complete local submissions and HTML; DuckDB 1.5.5 stores exact observation
nanoseconds and executes the anchored claim-selection SQL. The project adds
fixed source witnesses, immutable manifests and a bounded receipt. It does not
introduce a generalized identity resolver. Native source fingerprints and the
request plan are included in each private derivation.

Existing Alpaca-py 0.44.0 remains the accepted acquisition client, with zero new
calls in this sample. Current `get_asset` status cannot establish the historical
listing and delisting intervals that are missing. Its bars `asof` chooses symbol
mapping, not information availability; the already accepted
[FB/META receipt](../../blueprints/us-equities/identity-readiness/native-receipt.json)
is retained as separate query evidence. No bulk asset scan is justified.

WRDS/CRSP remains conditional as recorded in the
[earlier review](security-identity-review.md): the open Python client does not
supply an account, licensed dataset or redistribution rights. No entitlement was
inspected or presumed. Current licensed histories, even if later obtained, would
still need vintage and revision evidence before an as-known reconstruction.
This wave rejects historical-universe acceptance for missing complete security
coverage, permanent crosswalks, original availability, revision ordering and
permitted dataset access. It preserves useful issuer/exchange event facts and a
strict observation-time proof while those gaps remain open.

Public web research succeeded for the rendered filing documents. Direct web-tool
reads of the Form 25 raw XML and complete submission initially failed; these were
research-tool diagnostics, not evidence that the filings did not exist. The
coordinator's subsequent fixed native capture and receipts are authoritative for
its own requests. No research step inspected price performance or backtest
outcomes, and no source observation establishes trading permission.
