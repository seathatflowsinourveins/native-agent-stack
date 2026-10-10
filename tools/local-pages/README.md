# Local engineering pages

`build_pages.py` presents the CC current view, native readiness receipts,
gap board, roadmap, fleet, architecture and sources as seven complete local HTML documents. It uses the existing
`tools/north-star/build_readiness.py` functions `build`, `render` and
`render_fragment`; it adds presentation and refresh custody without deciding
gate acceptance. The initial reference is repository commit
`af7a4fe65f724e480bf0c79f0795de40a181b37d`. Each refresh records the actual native
builder and source-index hashes, so an explicitly selected newer checkout can
be traced without presenting its source change as reader approval or landing.

Run a finite refresh using the installed Python runtime:

```sh
nice -n 10 ionice -c2 -n7 python3 tools/local-pages/build_pages.py \
  --root /path/to/native-source-checkout \
  --state-root /path/to/native-state \
  --output-dir /path/to/native-state/coordination/command-center/local-pages \
  --receipt /path/to/native-state/research/local-pages/refresh-receipt.json
```

`--root` selects native readiness code and its default source index. Assets
always come from `assets/` beside this composer, independent of the selected
source checkout. `--sources` selects a native source index confined to that
checkout. `--gaps-source`, `--roadmap-source` and `--roadmap-inputs` select only
the exact paths approved for their role in the committed `source_policy.json`.
The policy currently approves the default state-root files:
`coordination/command-center/cc-tools/gaps/gaps.json`,
`coordination/command-center/cc-tools/roadmap/roadmap-status.json` and
`coordination/command-center/cc-tools/roadmap/roadmap-inputs.json`, respectively.
The flags do not grant access to other files, even inside the selected roots.
With no output or receipt flags, output defaults to `coordination/command-center/local-pages`
and receipt defaults to
`research/fullspeed-20261008/g5-stars-gap/local-pages/refresh-receipt.json`
under the chosen state root.

The Fleet page uses the supported read-only
`coordination/ns2604-coop/tools/fleet_block.py --json --no-gh` producer on
each refresh. Direct values fall back to the dated
`coordination/ns2604-coop/watchers/fleet-now.json` snapshot if collection
fails. The co-op's named subagents always use that snapshot and its own time,
because a direct invocation cannot observe them. CC named agents come only from
`cc-now.json#/cc_agents/running` and its own published timestamp; the producer's
different CC list is a separate observation. Tier, version holds and parking policy come from
`command-center/lane-tiers.json`. Parked CLI versions remain unreported when
the source supplies no observation; policy versions are separate.

`fleet_data.py` projects whitelisted labels/counts from those native sources,
omitting prompts, task text, emails and credential fields. Pool labels accept
the producer's anonymous `position N`, `fresh(HH:MM:SS)` and reset-time forms;
arbitrary account identities are rejected. A missing
`coordination/api-actions-20261008/api-actions-ledger.jsonl` displays UNKNOWN;
only a valid empty ledger establishes no recorded spend. Unknown roster sections,
tiers, ceilings and job counts remain UNKNOWN rather than zero. Existing ledger
rows contribute explicit per-event `actual_usd` and `max_usd` fields, matching
the native producer. Actual amounts are summed as spend; summed `max_usd`
reservations remain separate from the CC-owned credit ceiling. Unrecognized
ledger formats remain UNKNOWN.

Actions use one native `gh run list` invocation for the newest 100 repository
runs, then filter against checked-out workflow files that actually invoke a
model. Only workflow/status/time/run-ID fields are requested; prompt-like
display titles and branch names are omitted. The native CLI has no cache flag
for this command, so a 540-second nonserved JSON cache with a native file lock
coordinates refreshes. Fresh cache hits make no additional CLI request;
failure preserves earlier observations with their original time, never an
invented zero. The Fleet section identifies its bounded Actions scope.
Each source, producer, workflow, ledger, cache and lock path rejects symlinks
and nonregular inputs. Cache writes use securely created temporary files in
the cache directory and an atomic replace of a checked destination.
The producer executes only its verified bytes from a sealed Linux memory
descriptor, with its original file location, arguments and sibling-import
path. The child starts with Python isolated mode (`-I`), then adds the approved
producer sibling directory after verification. Bootstrap stdlib imports cannot
be shadowed by the page process's working directory or ambient Python path.
A dedicated process session has a 90-second limit; timeout cleanup kills its
descendant process group. Execution digest and byte count are retained;
collection never reopens the original producer pathname after validation.

Fleet tracking extends that collector with the native hcom roster and local
observability sources. A safe `hcom list --format ...` projection
captures all listed agents without reading prompts, config, argv or account
data or depending on a particular lane remaining registered. Valid rows retain
the native `launching` and `error` states; invalid rows leave other rows
available. Creation epochs display as UTC. The current roster remains separate
from historical `ecosystem_lane` labels in telemetry. Query failures, empty
metric results and unqualified counter zeros stay UNKNOWN.

Prometheus at recorded port 21090 supplies five-minute native counter rates.
Each client and token category remains separate because token categories
overlap. The invocation view covers API requests, tool calls, MCP calls, skill
invocations and agent invocations for each published client. Codex API attempts
(including retries), tool calls and MCP calls use their qualified native
counters; each unqualified numeric source remains explicitly unreported.
Numeric rates are labelled reported or lower bound. Codex counter rates remain
lower bound until deployed start-timestamp ingestion and a newly born
single-turn series read-back pass; a zero under that limit is unreported.
Rates apply `rate` before aggregation; a companion
`timestamp(counter)` query retains source scrape time separately from query
evaluation. A fresh selected scrape does not establish last invocation time
or complete coverage of every writer.

Native Loki at port 21300 supplies separate Claude API-request-record and
tool-result-record rates through numeric `rate(...[5m])` queries. These retain
their query-window bounds and evaluation time; last event time and complete
invocation coverage are unreported. Failed results and outer code-mode tool
records remain tool-result observations, not MCP counts. Loki-only lane labels
are retained. Missing, invalid and unqualified zero rates remain UNKNOWN. Raw
log streams, arbitrary labels and diagnostic payloads are not projected.

Model-service rows retain their source scope. Selected user-manager properties
observe `vllm-embed.service` without reading its unit body, environment or
arguments. Hindsight's documented health route measures DB reachability;
ai-memory's route measures process-listening liveness. The vLLM `/v1/models`
route uses host port 28231, measured by the command center. Its body-unread
HTTP observation measures model-list API reachability;
named-unit state and independent Prometheus scrape retain their separate
scopes; embedding readiness remains unqualified. Native HTTP reads use
recorded loopback endpoints, bounded responses, no proxy and no redirects;
health/model-list bodies are not read. Grafana port 21301 provides anonymous search
metadata for existing dashboard links. Per-lane Explore links use the supported
`panes` JSON and `schemaVersion=1` URL contract with the qualified
`ns2604-prometheus` datasource for native counter expressions and `ns2604-loki`
for Claude LogQL expressions, with each pane's observation range. The exact
Grafana 13.2.3 serializer and URL contract are pinned in the Fleet decision.
Dashboard lane-variable parameters remain unqualified.

The optional `fleet-tracking/1` member contains source dates, metric units,
window and query availability. Its explicit CLI/query/probe seams keep all
synthetic tests independent of runtime state. Failure of one optional source
leaves the existing Fleet observations available and displays tracking as
unreported with its reason. Shared sanitization applies before escaping fields
and links; complete markup is preserved.

Optional memory totals accept a finite positive scalar or a
`{value_gib, read_utc}` record. An invalid total becomes UNKNOWN with a reason;
valid mandatory readings still publish. A valid per-figure total keeps its
own recorded time rather than inheriting another measurement's date.

Mandatory fallback readings accept scalar or per-figure values. Invalid
figure dates become unreported with a reason rather than aborting publication.
An optional Fleet adapter failure also leaves all pages available with explicit
UNKNOWN observations. Known empty pool/session lists remain separate from
missing observations. Personal labels are masked as source text at identifier
boundaries (minimum length three), after counting; finished HTML tags are never
rewritten as personal identifiers. Classified decoded values retain the native
portable path/session/task substitutions and their surrounding source text.

Missing or partially written Adoption snapshots degrade only that section to
UNKNOWN. Producer-provided `codex_by_role` is preferred; an absent role projection
is labelled as a dated instance-label fallback. Raw keys still determine
memberships and counts before the shared display sanitizer masks personal paths,
host labels and positively classified encoded identifiers. Reads in flight use
the producer's name-and-tier format; actual zero subagents remains zero. Summed
per-account pool percentages are labelled with their reference rather than as
a unique aggregate pool, and ledger observations keep their actual source time.

The native refresh runtime needs the installed hcom, Claude and gh directories
on PATH for the upstream producer and Actions command. This is runtime setup
in the owned systemd unit, separate from client configuration or exporter
installation. The Fleet view uses local assets and the existing refresh timer.

Mapped tier/CLI values from `lane-tiers.json` appear beside running observations
when they differ. Columns identify the order as running / map; the renderer
shows the mismatch without changing a lane's tier or version. CC `api_credit`
supplies the ceiling and stop/report threshold; planned table amounts are
labelled estimates. Recorded actual spend uses the native producer's
`api_spend_ledger.sums.actual_usd`, not the sum of reserved caps.

`adoption_view.py` reads the CC-owned
`coordination/command-center/pages/adoption-now.json` (`adoption-now/1`).
Readiness shows layer/server activity. Fleet groups Codex instances into lane
roles using dated launch windows from the co-op registry, with the instance
mapping collapsed by default. Ambiguous labels remain unattributed and the
published call/population totals are conserved. Claude and Codex orchestration
and measured `sdk:` rows retain their source values; absent SDK measurements
remain unreported. The co-op alone runs its hourly collector;
page refreshes make no Loki query or collector invocation. Exact server
aliases follow the producer's memberships and each raw server row counts
once. Sparse maps show zero recorded calls, while unknown values stay
unreported. Counts describe the stated retrospective window and do not prove
adoption acceptance, fresh-session use or workflow improvement.

`architecture_builder.py` generates `architecture.html` from the canonical
catalogs named by `catalogs/landscape/manifest.json`, the current retained G5
asset, exact source metadata inventories and the hashed hourly Adoption
snapshot. Full mode requires one section per canonical layer; `--first-layer`
supports an early source-complete preview without changing the canonical
count. Selected choices, winners, alternatives, rejection reasons and pins
remain dated source records. Grand candidates stay pending G5 while the CC
gate is not MET. The four program stages come from `cc-now.json`; missing
per-tool stage data is unreported. Readiness labels dated selections as catalog
pins and shows observed host-version differences with their source time.

Inventory rows use canonical winner component-ID and candidate repository
joins, followed by the reviewed `architecture_mapping.json` for remaining
skills, agents, workflows and runtime automation. Each remaining unmapped item
has its specific reason. File/hash equality remains metadata provenance.
Hook and cron registrations come only from the CC's sanitized
`coordination/command-center/pages/automation-projection.json`; its digest and
stated limits are bound in the receipt. The reader does not open raw hook
sources, client configuration, credentials, env files or crontab contents.

State-root host receipts come only from the CC's sanitized
`coordination/command-center/pages/host-receipts-index.json`. Its path/hash and
each index-provided title/path/hash/byte count/mtime are retained in a separate
collapsed detail table labelled `local host receipt (state root)`. Receipt
hashes are declared by the index and mtime is file metadata; no referenced
markdown bodies are opened, and no execution date, command, result or E2E
acceptance is inferred. The mixed `e2e-truth-20261006` directory is excluded.

Architecture's native manifest identity and instance-to-role mapping come from
the retained `research/fullspeed-20261008/g5-stars-gap/local-pages/refresh-receipt.json`
projection. Its own path, byte hash and generation date are bound separately
from the reported native manifest hash. Architecture does not call the native
readiness builder against the state root or follow that projection's input
paths. Retained role attribution keeps its observation window; a different
invocation window retains published counts with attribution marked unassigned.
The complete inventory input set is declared in `inventory_sources`, with
computed hashes/bytes for approved content, and separate metadata-only
observations for user agent and service configurations. No user configuration
body is opened or hashed. Metadata-only entries have no computed content hash
and an explicit scope reason. Aliases are labels only after their canonical
target has independent approval.

Architecture source, projection and registered receipt selections also bind
independent exact roles in `source_policy.json` before parsing or hashing.
The shared bounded reader rejects leaf and ancestor symlinks. A protected or
unapproved catalog or receipt stops publication while preserving the last
successful output. Immutable Adoption candidates require the exact
`adoption-now-[a-f0-9]{16}.json` form in the reviewed snapshot directory before
any byte read; invalid names are ignored, and symlink candidates are refused.
An approved receipt above its existing read limit remains explicitly unmeasured
without widening that limit. The G5 archive is hashed and streamed to zstd
through its authorized descriptor, which avoids reopening its pathname.

Inventory uses that same independently approved reader for every content
hash and metadata parse, including its catalogs, manifests, checksum lists,
mapping and sanitized automation projection. The committed
`architecture_inventory` role contains 132 exact content paths; installed user
content is restricted to exact `SKILL.md` assets. The separate
`architecture_inventory_metadata` role contains 94 exact user agent/unit paths
and cannot authorize a content open. Native descriptor-relative no-follow
stat supplies their file metadata. Shared protected checks apply to both
lexical and canonical paths before reads. Ordinary unapproved discoveries are
reduced to counts by source root and kind before public inventory, custody or
detail rendering, with no candidate stat, resolve, open or hash. Individual
unapproved names and paths never enter served documents. Their asset presence
and runtime use remain unmeasured. Protected input
or a poisoned known alias still refuses the Architecture observation; the
composer preserves its last page while refreshing the other documents, or
publishes an explicit UNREPORTED placeholder on its first failure. Hashes and
parsed metadata derive from the same captured approved bytes. Unknown names
enter only cache signatures outside the serving root, so additions, removals
and renames invalidate the observation without publishing those names. Each
successful Architecture publication removes superseded generated detail HTML
from its fixed architecture/layers namespace before replacing the receipt;
cache reuse also removes details outside its retained output set.

`scripts/local_pages_policy_grants.py --pin <full-source-sha>` prints a static
proposal from native Git tree/registered-path metadata for review. Runtime
discovery never adds a grant. Receipt proposals also apply the pinned frozen
eligibility declaration from the repository tripwire. The receipt grant set
was reviewed at `c945ea1f011e4c7e69a0b5f19052717b2af9d46e`: removing the two
unused frozen permissions leaves 4648 exact JSON receipt paths. This remains
the reviewed pinned union; the current main proposal's 4725 eligible paths
do not add permissions without independent review.
Derivation does not open referenced receipt or frozen artifact bodies and
does not add descriptive-pin exceptions. Separately reviewed user canonical
filenames are metadata during permission generation. The shared reader uses
64 KiB chunks so a large logical bound does not allocate that bound for a small
file. Inventory cache signatures bind approved bytes, metadata tuples and
the policy digest before a prior render can be reused.

`inventory_user_names.json` contains only independently reviewed bindings
and safe provenance that reproduce the 41 skill, 94 metadata and one design
grant. Its source pin is the landed squash commit
`f96f2cd2decef021c259d853d442956dc73f1ecf`, reachable from `origin/main`;
the reviewed binding bytes are unchanged from the CC-read head. Pins must
remain reachable from `origin/main` after squash merging; ancestry confined
to a PR branch or PR merge ref does not qualify. User directory listings and
unapproved names are not committed.
Runtime discoveries never create permissions. The 33 exact alias
bindings name an already approved canonical target; the reader must verify
that target before any content or metadata observation. The CI grant test
compares committed repo grants with `inventory_paths(git ls-files)`. The
authorized landing rebase onto main `3c01bdddc66896f8e36f9f21d452710808a9557e`
retains the reviewed workflow paths and adds the committed host-name scanner,
yielding 90 repository grants. Regenerate the proposal after an authorized
rebase, using committed paths rather than runtime discovery. No raw user file
body is used for these derivations.

Directory-listing failures remain UNREPORTED rather than implying an empty
inventory, and unapproved rows receive no name-based evidence joins. Optional
Architecture archive/time-limit failures and Adoption attribution failures
leave the other pages available; receipts expose exception categories only.

Adoption role attribution uses the same native protected-name and no-follow
parent/leaf descriptor reader for fixed registries and reviewed receipt
families. Parking enumeration opens only its named directory with no-follow
semantics. Refused/missing/malformed metadata contributes an UNREPORTED source
error and no binding, source hash or invented attribution; published call
counts remain measured even when a role cannot be assigned.

Each component row reports observational use from the retained hash-verified
snapshot. Client components use session counts; unmeasured rows explain the
producer boundary, including missing Bash-run CLI counters. Registered receipts
are verified against `manifests/evidence.json` `files[]` hashes; the class falls
back from the receipt and registration `evidence_class` to `kind`. The newest
receipt retains its date, command count/program, result and path/hash, including
failures or an absent result field. Native host E2E and local receipts remain
distinct from vendor test-suite runs. Receipt presence, metadata completeness
and a successful qualifying result are separate facts.

The initial HTML contains layer choices and closed detail summaries. Component
tables are generated as per-layer pages and fetched only on expansion, using
native [HTML details](https://html.spec.whatwg.org/multipage/interactive-elements.html#the-details-element)
and [Fetch](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API/Using_Fetch).
Every component table stays collapsed with its count in the summary. Each
summary links the ordinary detail page as a fallback; failed loads can be retried.
The builder enforces initial HTML below1,500,000 bytes and records HTML/detail
sizes. Installed Playwright's native browser measures the served response and
checks deferred loading separately from the Python fixture contracts.

The existing refresh service rebuilds Architecture on a changed hourly
snapshot or relevant source/code metadata, and otherwise uses its nonserved
receipt/cache. Source hashes, installed frontend-design path/pin/hash, builder
and helper hashes, canonical/rendered counts and mapping coverage remain in
the Architecture receipt outside the serving root. The G5 archive is read
through the installed zstd stream without extraction; unrelated raw members
are not consumed as content.

```sh
nice -n 10 ionice -c2 -n7 timeout 600 python3 tools/local-pages/architecture_builder.py \
  --root /path/to/native-source-checkout --state-root /path/to/native-state
```

`--current-source` selects the exact approved read-only `cc-now/1` JSON path,
currently only `state-root/coordination/command-center/pages/cc-now.json`.
Another path requires a separately reviewed committed policy grant. It supplies the
readiness page's compact current view and the index's shared gate strip.
The CC-owned headline, gate count, estimate and basis are presented as recorded.
Events and owner deadlines show America/New_York first and UTC second, using
Python's `zoneinfo` with the date's actual daylight-saving offset. Manifest
cards keep their original dated states; a recorded, older observation that
differs from the current gate or its split successors adds “superseded in the
current view.” Unverified, undated, equal-time and newer observations are not
marked superseded; a recorded state disagreement without an older source date
says “differs from the current view.” Sources and
long per-input date lists are on `sources.html`, linked from each page.

`workstation.py` uses the installed Prometheus HTTP API at
`http://127.0.0.1:21090` to read exact available-memory and swap metrics when
present. Ambiguous, missing, stale or invalid series retain the CC's value
and read time. Each displayed figure identifies its provenance and timestamp;
no free-memory metric is relabelled as available. Requests have finite server
and client bounds. Query identity, sample metadata and any API error are
retained in the nonserved refresh receipt. There is no new exporter or dependency.
Windows metrics use job `workstation-windows`; the page composer selects node
metrics from `workstation-node`. Small nonzero swap values display in MiB so
they do not round to zero. Port19090 belongs to another mirrored WSL distro
and is never queried; earlier absence observations at that port do not describe
this host. The corrected source identity is backed by native process readback
on21090 and its installed Prometheus API, not merely a responding socket.

All input reads and rendering complete before publication. Generated HTML and
assets are prepared in nonserved staging, then each destination is atomically
replaced with `os.replace`; the receipt is replaced last. This is atomic per
file, not a transaction across all page files. Required source or rendering failure
keeps the prior generated bytes and prior receipt; optional Fleet or Adoption
observations instead degrade their own fields to UNKNOWN. An I/O failure during the
replacement sequence can leave files from two refreshes; compare their visible
refresh time and manifest hash with the last receipt and run a successful
refresh again. Unrelated files in the served root are preserved. Symlink
sources/destinations, inputs inside the served root, receipt paths inside that
root and destinations overlapping inputs are rejected. The receipt records
source paths, input hashes and generated output hashes without copying source
bytes into the served directory. No source CC HTML or JSON is overwritten.

Every page distinguishes its generated refresh time from source-owned dates.
The gap page preserves `updated_utc`; the sources page lists the date fields
in each retained input when available. A roadmap without a source-owned snapshot date
says so and identifies its file modification time as file metadata. Milestone
dates remain event dates. The SHA on every page is the SHA-256 of the JSON
produced by native `render`, rather than an invented readiness digest.
Milestones preserve either a source `at` timestamp or the source `when` label,
following the custodian's `cc-tools/roadmap/build_roadmap.py:284` schema. Relative
`when` labels are displayed verbatim without inventing an ISO date. A milestone
with neither timing field stops the refresh.
Missing native retained receipts remain `UNVERIFIED` under the native builder's
existing semantics. Gap/roadmap/current-view source failure stops the refresh.

The pages load only the local stylesheet and script. Navigation, a labelled
system/light/dark selector and gap search/group/severity filters are their
interactive controls. Gap search and filter values use the URL parameters
`q`, `group` and `severity`, so a filtered view can be shared and reopened.
Filter choices create browser history entries; Back and Forward restore them.
Typing replaces the current entry to keep history from growing per keystroke.
Roadmap `owner`/`rules` direction arrays, unsupported
narrative placeholders and account artifact URLs are omitted from the view;
omission reasons and source pointers are recorded in the nonserved receipt.
Reference keys bind exact approved files before any read; keys with no safe
allowed file, including references into mixed capture directories, are omitted
and recorded. A shared sanitizer applies the native portable home/session/task
projection and account URL policy to every served page string, including native
manifest gate cards and fragments. Custody receipts keep their original paths.
The independently committed `source_policy.json` binds every native source-index
key, the source-index file itself, and linked supporting/SDK/raw receipt roles
to exact permitted paths. Selecting JSON cannot extend it. The guard checks
each path before the original native reader opens it and uses bounded regular
file reads that reject symlinks. Policy provenance and hashes are retained.
Source custody uses raw receipt paths; portable copies are used only for rendering.
All four source overrides bind independent exact approved paths within the
selected repository or state root before native reads or source capture.
Credential, environment, client-secret and mixed capture paths are refused.
An owner URL changed by sanitization renders as plain text.
Operational owner fields remain source records. The original CC fragment's
external fonts and attributed direction are not used.

Run the focused local-page modules and native readiness checks:

```sh
nice -n 10 ionice -c2 -n7 timeout 600 python3 -m unittest discover -s tests -p test_local_pages.py
nice -n 10 ionice -c2 -n7 timeout 600 python3 -m unittest discover -s tests -p test_local_pages_workstation.py
nice -n 10 ionice -c2 -n7 timeout 600 python3 -m unittest discover -s tests -p test_local_pages_current_view.py
nice -n 10 ionice -c2 -n7 timeout 600 python3 -m unittest discover -s tests -p test_local_pages_sanitization.py
nice -n 10 ionice -c2 -n7 timeout 600 python3 -m unittest discover -s tests -p test_local_pages_source_policy.py
nice -n 10 ionice -c2 -n7 timeout 600 python3 -m unittest discover -s tests -p test_local_pages_policy_grants.py
nice -n 10 ionice -c2 -n7 timeout 600 python3 -m unittest discover -s tests -p test_north_star_readiness.py
nice -n 10 ionice -c2 -n7 timeout 600 python3 -m unittest discover -s tests -p test_local_pages_fleet_data.py
nice -n 10 ionice -c2 -n7 timeout 600 python3 -m unittest discover -s tests -p test_local_pages_fleet_execution.py
nice -n 10 ionice -c2 -n7 timeout 600 python3 -m unittest discover -s tests -p test_local_pages_fleet_regressions.py
nice -n 10 ionice -c2 -n7 timeout 600 python3 -m unittest discover -s tests -p test_local_pages_fleet_view.py
nice -n 10 ionice -c2 -n7 timeout 600 python3 -m unittest discover -s tests -p test_local_pages_fleet_tracking.py
nice -n 10 ionice -c2 -n7 timeout 600 python3 -m unittest discover -s tests -p test_local_pages_fleet_tracking_view.py
nice -n 10 ionice -c2 -n7 timeout 600 python3 -m unittest discover -s tests -p test_local_pages_adoption.py
```

The fixtures use the repository's real native builder and local temporary
receipts. They need no external network, shared service, credentials or
third-party packages; the redirect tests bind an isolated loopback socket.
Browser interaction and actual host reachability are separate co-op checks.

Primary references: the native readiness API at the commit above; the retained
`command-center/cc-tools/gaps/gaps.json`, `roadmap/roadmap-status.json` and
`roadmap/roadmap-inputs.json` schemas; Python 3.13's documented
[`html.escape`](https://docs.python.org/3.13/library/html.html#html.escape),
[`os.replace`](https://docs.python.org/3.13/library/os.html#os.replace),
[`tempfile`](https://docs.python.org/3.13/library/tempfile.html) and
[`importlib.util`](https://docs.python.org/3.13/library/importlib.html#importlib.util.spec_from_file_location),
[`zoneinfo`](https://docs.python.org/3.13/library/zoneinfo.html), and the
[Prometheus3.15 query API](https://prometheus.io/docs/prometheus/latest/querying/api/#instant-queries).
The exact exporter metric contracts and pins are recorded in `workstation.py`.
The Fleet source contract is `coop-fleet/1` from the native producer above;
the privacy projection also follows read-only `cc-now/1` and `lane-tiers/1`.
Native Actions reference: [gh2.102.0 run-list source](https://github.com/cli/cli/blob/v2.102.0/pkg/cmd/run/list/list.go)
and the [upstream command manual](https://cli.github.com/manual/gh_run_list).
Cache locking uses Python3.13's [`fcntl`](https://docs.python.org/3.13/library/fcntl.html).
