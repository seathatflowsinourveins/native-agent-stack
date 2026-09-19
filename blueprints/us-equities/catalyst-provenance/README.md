# Native EdgarTools and catalyst provenance

This wave adopts **EdgarTools 5.58.0** in an isolated environment and executes its
native interfaces. The official SEC metadata request returned **HTTP 403**. The
network branch stopped. Accepted offline results are a two-member synthetic
index/parser example and one real historical 8-K HTML fixture from the pinned
upstream repository. Neither is a newly acquired historical trading dataset.

The upstream fixture is accession `0000887919-21-000012`, at release commit
`abe44344c56cf4bfb5443e0debca7e39342f6e7a`. Native `HTMLParser().parse(raw)` then
`Document.to_markdown()` converted 32,434 source bytes into 5,325 Markdown bytes.
The original bytes are hash-verified. The checked-in text has one final newline
added by the file writer; the adapter removes that one byte and verifies the
original upstream hash before parsing. Missing SGML acceptance metadata leaves
this real document quarantined at every trading cutoff. Byte reduction does not
measure model-token savings or predictive merit.

## Native adoption and commands

Use a new private runtime directory outside the repository. The lock contains
the 42 packages resolved for this Linux/Python 3.13 acceptance; another machine
must repeat native acceptance rather than inherit this host's result.

```sh
uv venv "$CATALYST_RUNTIME/sdk" --python 3.13
uv pip install --python "$CATALYST_RUNTIME/sdk/bin/python" \
  -r blueprints/us-equities/catalyst-provenance/requirements.lock
```

Keep an honest declared identity in the local SEC contact environment file;
source only that file. Native EdgarTools consumes `EDGAR_IDENTITY`, while the
existing financial-data recipe consumes `SEC_USER_AGENT`. This host configured
a truthful public project issues URL, not an invented personal email. The native
SDK accepts that string; its quickstart recommends an email contact, and SEC's
example header also uses an email. String acceptance does not establish SEC
access or equivalence to that recommendation.

```sh
set -a
. "$SEC_CONTACT_ENV"
set +a
export EDGAR_IDENTITY="${EDGAR_IDENTITY:-$SEC_USER_AGENT}"
EDGAR_LOCAL_DATA_DIR="$CATALYST_RUNTIME/native-cache" \
  timeout --signal=TERM --kill-after=5s 60s \
  "$CATALYST_RUNTIME/sdk/bin/python" \
  blueprints/us-equities/catalyst-provenance/native_edgar.py \
  --out "$CATALYST_RUNTIME/native-network.json"
```

This invokes upstream
`edgar.get_filings(2020,1,form="8-K",amendments=True,filing_date="2020-03-02")`.
The upstream call downloads the quarterly index and filters afterward; selecting
five results is not a five-row download limit. The isolated process disables
automatic retries with upstream `stamina.set_active(False)`, uses the native
two-per-second rate setting and 15-second HTTP timeout, and runs under a 60-second
outer timeout. Empty proxy environment values are omitted only inside this
process because the native HTTP manager rejects an empty URL; all nonempty
proxy settings remain unchanged. No proxy or access bypass was introduced.

Native attempts retained in [receipt.json](receipt.json): the first failed
before HTTP due to an empty proxy URL; the corrected invocation observed one
HTTP 403 from the SEC quarterly-index endpoint. Do not repeat an unchanged
refusal. The acquisition wrapper records SDK metadata and a bounded native
context summary on success; it does not capture the raw quarterly index and
therefore is not by itself immutable raw-source provenance.

These commands are offline and need no sign-in:

```sh
"$CATALYST_RUNTIME/sdk/bin/python" \
  blueprints/us-equities/catalyst-provenance/native_edgar.py \
  --fixture blueprints/us-equities/catalyst-provenance/fixture.idx \
  --out "$CATALYST_RUNTIME/native-offline.json"
"$CATALYST_RUNTIME/sdk/bin/python" \
  blueprints/us-equities/catalyst-provenance/native_document.py \
  --out "$CATALYST_RUNTIME/native-document.json"
python3 -m unittest tests.test_catalyst_provenance
```

The first calls pinned upstream `read_pipe_delimited_index`, `Filings.filter`
and `Filings.to_context(detail="minimal")`. The second parses the real upstream
fixture locally; its source identity, hashes and first local observation appear
in [upstream-8k-source.json](upstream-8k-source.json). Output files are exclusive;
use a fresh output name for a justified new run.

## Causal bridge and future acquisition

[catalyst.py](catalyst.py) is a small custom contract bridge, not an upstream SEC
SDK. It has synthetic behavior acceptance and real-fixture quarantine acceptance.
Its direct SEC acquisition was **not executed after the 403**.

The predeclared cohort is all 8-K/8-K/A entries in the 2020-03-02 daily master index.
It retains full raw index bytes, validates the day/path/identities, sorts by
CIK/accession, and selects at most five headers. That cap is an acquisition
sample, never a historical trading universe. Every amendment retains its own
accession. Failures remain explicit and stop later requests. Each run is new;
previous runs/files are never overwritten. `first_observed_at` means response
completion for this acquisition run, not a globally earliest observation across
all previous runs.

Availability is the latest of qualified acceptance time and completion of both
required local source observations. SEC's raw Eastern header timestamp is kept
separately; timezone conversion uses `America/New_York` and quarantines ambiguous
or nonexistent DST times. The selected winter index date avoids that ambiguity.
Missing or mismatched accession/form/date/timestamp is quarantined. Daily index
dates, report dates, acceptance, website dissemination, and our receipt time are
not interchangeable. SEC explicitly does not guarantee dissemination lag.

The offline packet re-hashes the index and every header, reconstructs the cohort
and events, and rejects pre-observation cutoffs. Future use, only after access
conditions materially change, is:

```sh
timeout --signal=TERM --kill-after=5s 180s python3 \
  blueprints/us-equities/catalyst-provenance/catalyst.py acquire \
  --root "$CATALYST_RUNTIME/acquisitions" --run-id first-access --member-limit 5
python3 blueprints/us-equities/catalyst-provenance/catalyst.py packet \
  --run "$CATALYST_RUNTIME/acquisitions/first-access" --as-of "$AS_OF" \
  --out "$CATALYST_RUNTIME/packet.json"
```

Responses are bounded to 5 MiB for the index and 1 MiB per header; retries and redirects are refused.
An external deadline remains necessary for operating-system/DNS stalls.

## LLM-native scope and source roles

Use native `Filings.to_context(detail="minimal")` on a bounded selected subset;
the real document path uses native Markdown conversion. Keep these artifacts
outside the always-loaded prompt and let Codex/Claude retrieve them on demand.
No new MCP server, hook, login store, model route or bulk corpus is installed.

The current pin's source/documentation covers 8-K material-event disclosures,
Forms 3/4/5 insider reporting, beneficial-ownership 13D/G, institutional 13F,
and XBRL financial statements. Those are complementary research sources with
different filing delays and revisions. This wave executed only the described
index/8-K paths; it did not accept the other form parsers or infer incentive
signals, current float, issuer history or tradable pre-positioning knowledge.

Primary references: [release](https://github.com/dgunning/edgartools/releases/tag/v5.58.0),
[MIT license](https://github.com/dgunning/edgartools/blob/abe44344c56cf4bfb5443e0debca7e39342f6e7a/LICENSE.txt),
[pinned native API](https://github.com/dgunning/edgartools/blob/abe44344c56cf4bfb5443e0debca7e39342f6e7a/edgar/_filings.py),
[SEC access](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data),
[SEC timestamps/reuse](https://www.sec.gov/about/webmaster-frequently-asked-questions).
