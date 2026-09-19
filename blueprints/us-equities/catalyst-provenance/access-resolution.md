# SEC access resolution

The tested SEC archive path now works with the user's monitored contact stored
privately. Native EdgarTools 5.58.0 completed its full quarterly-index request and
selected 371 8-K/8-K/A index entries for 2020-03-02. No SEC login or API key was
needed. These are index rows; co-filers can share an accession.

The earlier 403 remains in its dated receipt. The contact changed and time
elapsed before the successful request, so this is observed access recovery,
not proof that the email alone caused it. The [new receipt](access-resolution.json) preserves both the
successful commands and intervening local failures.

The raw-source adapter completed six requests: one daily index and five selected
headers. The 371 entries contain 360 unique accessions (362 8-K rows and nine
amendments). Fresh offline packets re-hash all six sources: the historical cutoff
admits **0/5**, while the cutoff after local acquisition admits **5/5**. Their
acceptance timestamps are in 2020 and our first observations are in 2026.
All **236 local tests passed with zero skips**; both compatibility changes and
their 21 focused tests passed independent review.

## What was corrected

Both native identity variables now use the genuine monitored contact. The file
is private, mode 600, and sourced by the existing local environment loader.
The email is not part of this repository. A new shell or a command sourcing that
contact file receives the current value; no Desktop restart or account login
was required for these native commands.

Installed 5.58.0 accepts `edgar.set_identity(user_identity: str)` and
`EDGAR_IDENTITY`. Rate control uses `EDGAR_RATE_LIMIT_PER_SEC` before import.
Some documentation examples use different signatures; the accepted recipe is
based on the pinned implementation. Two requests per second remains the
configured maximum for this isolated acquisition process.

A deliberately bounded HTTP diagnostic received 200 but left a partial cached
stream. Installed httpxthrottlecache 0.6.1 promotes its stream cache in a `finally`
block without checking response completion. The subsequent cached gzip read
failed with EOFError. Only that isolated diagnostic cache was preserved and
renamed; no global cache was deleted. A fresh full native download then passed.
The complete compressed index is 5,079,824 bytes and passed gzip validation.
For future bounded stream diagnostics, close existing native clients before
using `http_client(bypass_cache=True)`; do not interrupt a cache-writing stream.

The first real daily-index acquisition exposed our adapter's synthetic-format
assumptions. The real source uses `File Name`, compact YYYYMMDD dates, older
dates on some non-target forms, and shared accessions across co-filers. The
compatibility fix validates actual dates and paths, applies the selected-day
contract to 8-K/8-K/A entries, and preserves separate CIK/accession identities.
Exact duplicate selected identities still fail. Real header documents also use
the native `<TYPE>` form field, which is validated alongside the existing text
header variants. Original refused and failed runs remain immutable.

## Native workflow

Use the already-adopted isolated environment. Supply fresh output/run names:

```sh
. "$SEC_CONTACT_ENV"
export EDGAR_IDENTITY="$SEC_USER_AGENT"
EDGAR_LOCAL_DATA_DIR="$CATALYST_RUNTIME/native-cache" \
  timeout --signal=TERM --kill-after=5s 60s \
  "$CATALYST_RUNTIME/sdk/bin/python" \
  blueprints/us-equities/catalyst-provenance/native_edgar.py \
  --out "$CATALYST_RUNTIME/native-network-contact-complete.json"

timeout --signal=TERM --kill-after=5s 180s python3 \
  blueprints/us-equities/catalyst-provenance/catalyst.py acquire \
  --root "$CATALYST_RUNTIME/acquisitions" \
  --run-id "$FRESH_RUN_ID" --member-limit 5

python3 blueprints/us-equities/catalyst-provenance/catalyst.py packet \
  --run "$CATALYST_RUNTIME/acquisitions/$FRESH_RUN_ID" \
  --as-of "$AS_OF" --out "$FRESH_PACKET_PATH"
```

The first command invokes upstream `edgar.get_filings` and native bounded
`Filings.to_context`. The latter commands are this repository's provenance
adapter, not an upstream SDK. Keep these evidence classes distinct.

## Remaining gates

A successful download does not establish when a past trading system received
the information. Retain immutable bytes, acceptance metadata, revisions and
local observation times. The current acquisition sample is not a complete
historical equity universe, validated mover signal or broker simulation.

The next data requirements are as-known security/identifier history, delisted
names, corporate actions and entitled prices/quotes/trades. Freeze a new
chronological study before scoring; the earlier ETF control segment is already
inspected. Paper credentials remain a separate deferred step.

For a future persistent refusal, stop the network branch and retain the exact
error privately. SEC's supported access-denied route is a report to its
webmaster with the error and source IP; no such message was needed or sent here.
Official submissions/companyfacts APIs are complementary feeds, not an assumed
replacement for filing bodies or complete historical availability.

References: [SEC access and contact guidance](https://www.sec.gov/about/webmaster-frequently-asked-questions),
[public APIs and bulk data](https://www.sec.gov/search-filings/edgar-application-programming-interfaces),
[pinned EdgarTools HTTP implementation](https://github.com/dgunning/edgartools/blob/abe44344c56cf4bfb5443e0debca7e39342f6e7a/edgar/httpclient.py).
