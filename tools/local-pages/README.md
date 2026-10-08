# Local engineering pages

`build_pages.py` presents the CC current view, native readiness receipts,
gap board, roadmap, fleet and sources as six complete local HTML documents. It uses the existing
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
because a direct invocation cannot observe them. CC named agents come from
`cc-now.json`; tier, version holds and parking policy come from
`command-center/lane-tiers.json`. Parked CLI versions remain unreported when
the source supplies no observation; policy versions are separate.

`fleet_data.py` projects whitelisted labels/counts from those native sources,
omitting prompts, task text, emails and credential fields. Pool labels accept
the producer's anonymous `position N`, `fresh(HH:MM:SS)` and reset-time forms;
arbitrary account identities are rejected. A missing
`coordination/api-actions-20261008/api-actions-ledger.jsonl` displays “no spend
yet”; an unknown ceiling or job count remains unreported. Existing ledger
rows contribute only explicit cumulative `spend_usd` and `ceiling_usd` fields.

Actions use one native `gh run list` invocation for the newest100 repository
runs, then filter against checked-out workflow files that actually invoke a
model. Only workflow/status/time/run-ID fields are requested; prompt-like
display titles and branch names are omitted. The native CLI has no cache flag
for this command, so a600-second nonserved JSON cache with a native file lock
coordinates refreshes. Fresh cache hits make no additional CLI request;
failure preserves earlier observations with their original time, never an
invented zero. The Fleet section identifies its bounded Actions scope.

The native refresh runtime needs the installed hcom, Claude and gh directories
on PATH for the upstream producer and Actions command. This is runtime setup
in the owned systemd unit, separate from client configuration or exporter
installation. The Fleet view uses local assets and the existing refresh timer.

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

All input reads and rendering complete before publication. Generated HTML and
assets are prepared in nonserved staging, then each destination is atomically
replaced with `os.replace`; the receipt is replaced last. This is atomic per
file, not a transaction across all page files. Source or rendering failure
keeps the prior generated bytes and prior receipt. An I/O failure during the
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
nice -n 10 ionice -c2 -n7 timeout 600 python3 -m unittest discover -s tests -p test_north_star_readiness.py
nice -n 10 ionice -c2 -n7 timeout 600 python3 -m unittest discover -s tests -p test_local_pages_fleet_data.py
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
