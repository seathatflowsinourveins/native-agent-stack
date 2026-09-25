# Data lake: governed historical backfill (source layer)

`backfill.py` fills the lake's raw source layer from Alpaca's historical REST API under a shared token bucket
(`--rate`, at most 6,000 requests/min so the live monitor, scans and the engine keep headroom under the account's
10,000/min data limit, measured 2026-09-24), with HTTP 429 back-off to the limit's reset. A response whose
`X-Ratelimit-Remaining` is under 3,500 pauses the bucket until the limit resets, so the headroom the budget table
reserves for the other pools holds whatever else is running (critique B10). GET only, to the fixed endpoint: a
redirect is refused before any follow-up request, since urllib would resend the key pair to the `Location` host (plain
http included), and environment proxies are ignored (D12's fixed-endpoint guard, as in `financial-data/sec_data.py`).
The data stays private (licensed market data and news) in an operator-chosen `--out` directory; an `--out` inside any
git work tree is refused. The design follows the 2026-09-24 data-and-execution convergence record (D1 lake
architecture, D2 minute bars; backlog items 7-8) and its completeness critique (X2-X4). Normalized Zstd Parquet is a
separate, later layer.

## Scope header: a changed scope never resumes

Every dataset directory `<out>/<dataset>/` carries `scope.json`, which the first run writes before any request:

| Field | Meaning |
| --- | --- |
| `code_sha256` | sha256 of the `backfill.py` that collects the dataset |
| `endpoint` | host and path |
| `fixed_params` | every constant request parameter; for `stock_bars_1min` including the universe's `asof` |
| `symbols_sha256` | sha256 of the planned task list (each task id with its symbols); `null` for `news`, which is not symbol-scoped |
| `span` | the requested `--start` and `--end` |
| `planned` | the planned task count and the sha256 of the planned task ids (`news`: the span's days) |
| `task`, `capture` | task unit (batch size, New York or UTC window) and raw capture mode |

`fingerprint` is the sha256 of that scope; `provenance` (creation time, universe file and source hashes, and for
`stock_bars_1min` the planned task ids, which must hash to `planned`) is recorded beside it but is not part of it.
Every page-capture manifest row repeats the fingerprint as `scope_fingerprint` (D1: each task carries its scope
fingerprint). A row naming another fingerprint never counts as done, so its task is fetched again, and `verify` reports
it. Each of these is refused with exit 2 before any request:

- a run whose scope differs in any field;
- a header that no longer hashes to its fingerprint;
- a manifest without a header, which was collected before headers existed. This directory is left untouched.

Collect a new scope, a new code version or an extended span into a new `--out` directory. This is the rule
`broad-universe/collect_daily.py` already applies. A full run is refused before any pilot without writing a header, so
a mistyped span does not pin the directory.

Also refused with exit 2 before any request:

- an `--out` inside a git work tree (any directory with a `.git` entry at or above it, symlinks resolved; this
  checkout publishes to a public repository);
- a `STOP` file already in `--out` (it drains a running run; a leftover one must not make later runs exit at once);
- a second backfill on this host, whatever its dataset or `--out`: every run holds a host-wide lease,
  `~/.local/state/native-agent-stack/data-lake/backfill.lock` (`flock`; the file names the holder), because the
  budget table runs the backfill pool one job at a time and a new scope always goes to a new `--out`;
- a second run on the same dataset (`<dataset>/.lock`).

## Datasets

| Dataset | Endpoint and fixed parameters | Task | Raw capture | Status |
| --- | --- | --- | --- | --- |
| `news` | `/v1beta1/news` (Benzinga via Alpaca), `include_content=true`, 50 per page, ascending | one UTC calendar day, 00:00:00Z to 23:59:59.999999999Z (the archive: to the next day's 00:00:00Z) | records | Backfilled 2015-01-01..2026-09-23 on 2026-09-24: the manifest holds 4,284 days, 2,217,343 records (2,217,341 distinct ids) and 46,650 pages (private; about 1.1 GB). Two runs wrote it: 2026-09-14..20 first (7 days, 3,910 records, 82 pages), then the other 4,277 days (2,213,433 records, 46,568 requests, 0 HTTP 429, 0 failed days, about 947 s at `--rate 3000 --workers 8`) |
| `stock_bars_1min` | `/v2/stocks/bars`, `timeframe=1Min`, `feed=sip`, `adjustment=raw`, `limit=10000`, `sort=asc`, `asof` = the universe's naming date (2026-09-21) | 100 symbols x one calendar month, from 04:00 ET on the first day to 19:59:59.999999999 ET on the last | wire pages | Code and synthetic tests only; not yet run against the provider |

### news: kept as collected (record capture)

- Each day file `news/<YYYY>/<MM>/<DD>.jsonl.gz` holds that day's records re-serialized with sorted keys (gzip, fixed
  mtime). These are not the wire pages.
- Each manifest row covers one day: records, pages, the day file's sha256, bytes and fetch time. Rows carry no request
  parameters and no code sha. The task is held in memory until the day is complete.
- The day file and its directory are fsynced before the row is appended (and fsynced). A day counts as done only while
  its file exists at the recorded size, so a crash that kept the row but not the file refetches that day.
- **Day bounds overlap in the archive.** Both `start` and `end` are inclusive (the `/v1beta1/news` reference), and the
  archive requested each day D as `D T00:00:00Z` to `D+1 T00:00:00Z`. A record created exactly at midnight is
  therefore stored in two day files. A read-only scan on 2026-09-24 (local integration) found 2,217,343 records but
  2,217,341 distinct ids: ids 5922230 (created 2015-10-19T00:00:00Z) and 17421821 (2020-09-09T00:00:00Z) each sit in
  that day's file and the previous day's. The archive is kept as collected. Summing day files double-counts those two,
  so the normalized layer dedupes news by `id`. New pulls end each day at `23:59:59.999999999Z` (recorded in the scope's
  `task.window_utc`), which is a different scope, so they go into a new `--out`.
- The 2015-2026 archive predates scope headers. It has no `scope.json`, so a news run into that directory is refused.
  - Its operator-written `run-header.json` records code sha256 `1119c92b…`, which is the committed `backfill.py` at
    `1d52ed21`, and the fixed parameters. Its `result` block pairs the archive's 4,284 days with the second run's
    record and request counts; the manifest totals above are the archive's.
  - `backfill.py verify news` re-hashed all 4,284 day files against the manifest on 2026-09-24 with 0 problems
    (local integration, read-only), again with this version (0 malformed or superseded rows; `complete: null`,
    since a header-less archive records no plan).
  - The archive is complete and needs no resume. An incremental pull goes into a new `--out` with its own header.
- `updated_at` changes after publication are not re-fetched. The live monitor records receive times going forward,
  and D5 normalizes revision timing.

### stock_bars_1min: page capture

- **Requests.** Every page is requested with `Accept-Encoding: gzip`.
- **Storage.** Each page is written as it arrives to `stock_bars_1min/<YYYY>/<MM>/b<NNNN>/p<NNNNN>.json.gz`, so memory
  stays bounded per page.
  - A gzip-encoded page is stored byte for byte as the wire delivered it.
  - An identity-encoded page is gzip-wrapped (fixed mtime) and labelled `content_encoding: identity`; the pilot
    reports pages by encoding, so an identity answer is visible.
- **Durability.** Each page file is fsynced before its rename, the task directory and its rename are fsynced, and each
  manifest append is flushed and fsynced. `scope.json` and `pilot.json` are fsynced with their directory, so the
  header survives any crash that keeps a row naming it. A task counts as done only while every page file its row
  records exists at the recorded size; otherwise (a crash that kept the row but not the pages) it is fetched again.
- **Manifest row per task.** Each row records:
  - the task's base request parameters;
  - per page: its `page_token`, file, `sha256` of the stored bytes, `json_sha256` of the decoded body, `wire_bytes`
    (as received), stored and decoded sizes, bar count, the actual `next_page_token` (null on the last page) and
    fetch time;
  - the bar total and `bars_by_symbol`;
  - `symbols_without_bars`: requested symbols that returned no bar (critique U11: a renamed or reused ticker may
    return nothing under `asof=2026-09-21`);
  - symbols the provider returned that were not requested;
  - `quarantined`, the exact count of quarantined bars, and `quarantine`, the first 100 of them.
- **Quarantine.** Bars stamped outside 04:00-20:00 New York time (for example a print stamped exactly 20:00 ET inside
  the month) are counted as quarantined, not dropped, and the task still completes. A month window also returns any
  overnight bars between its days, which D2 never measured, so a row lists at most 100 and stays bounded. The raw
  pages stay immutable and hold every bar, and the normalized layer excludes these bars.
- **Failures.** A task is recorded only when its page chain reaches a null `next_page_token`.
  - An interrupted attempt's pages sit in `b<NNNN>.part/` and are replaced when the task is fetched again.
  - A failed task is listed in the run result and retried on the next run of the same scope.
  - A page chain that repeats a token or passes 2,000 pages fails its task.
- **Verification.** `verify` re-hashes every page, decodes it, and checks:
  - that the scope header is present and intact, and that every row names the header's fingerprint;
  - the chain against the stored bodies: the first page has no token, each body's `next_page_token` names the next
    recorded page's token, and the last body's is null (a row cut short fails even when its files hash);
  - that each body holds the bars its page records, that pages sum to the task total, and that the bodies give the
    row's `bars_by_symbol` and `symbols_without_bars`;
  - the recorded tasks against the scope's planned ones: `planned_tasks`, `missing_tasks` (with examples) and
    `complete`. A task outside the plan is a problem. `ok` is false, and `verify` exits 1, while any planned task
    has no row, so a drained or pilot-only lake never passes as complete. A header-less news archive has no plan
    (`complete: null`).
  - A missing manifest or a malformed row is reported as a problem, not raised.
  - A task's (or news day's) last row decides; earlier rows for it (a refetch) are counted as `superseded_rows`.
    Decoding every page makes a full-lake verify a long read (on the order of the D2 volume of JSON; not measured).

### The asof-aware monthly universe

`backfill.py universe` builds the task universe from the materialized broad-universe daily dataset. It reads
`daily.parquet` after `coverage.dedupe_identity`, `plan*.json`, `ledger.jsonl` and `identity-dedup.json`, and needs
DuckDB (the research runtime); the backfill itself is stdlib-only.

- **Membership.** Month M holds every symbol with at least one daily SIP bar in M. This covers the asset master's
  active and inactive symbols plus the corporate-action supplement of delisted names absent from it. A delisted
  symbol stays in the universe through its last month, and a new listing enters with its first month. Each value is
  the symbol's daily-bar sessions that month, which the pilot uses to scale its projection.
- **Naming date.** The daily collector sent no `asof`, so the provider named every symbol as of the request date.
  - The builder takes that date from the ledger's request timestamps and refuses if they span more than one date in
    UTC or New York.
  - For the retained dataset every request fell on 2026-09-21, so `stock_bars_1min` requests `asof=2026-09-21`
    (`mover-early-entry/deviations.json` D2). With that date, `META` in 2016 returns Facebook's history. `FB`'s
    duplicate 2016-2022 rows were removed by identity deduplication, so it is not requested for those months.
  - A newer universe carries its own naming date, which changes the scope.
- **Coverage.** A span ending after the universe's last session (`covers_through`) is refused, because symbols first
  listed after it would be missed. A month missing from the universe is refused.
- **Selection.** Membership is derived from observed bars (which symbols traded). It is not a decision-time
  universe: research selection still goes through `point-in-time/select.sql` with explicit availability.

Local integration on the retained 2026-09-21 daily dataset: the build took 2.2 s at 0.5 GB peak RSS under
`ecosystem-bounded-run`. It gave the following, which match the broad-universe README and D2:

- 129 months (2016-01..2026-09), 17,997 symbols, 1,168,742 symbol-months and 24,195,741 symbol-sessions;
- 11,753 tasks at 100 symbols;
- for 2016-01-01..2026-08-31, 11,620 tasks and 24,024,163 symbol-sessions;
- symbols whose last daily bar falls in 2016/2017/2018: 25/47/167.

This is the pre-2020 survivorship gap. The delisting-coverage blueprint counts 378/296/268 common-equity Form 25-NSE
deregistrations for the same years. Names delisted before 2020 without Alpaca bars cannot enter this universe; the
`pre-2020-delisting` gate stays open.

### Pilot and disk gate

- **Pilot.** `--pilot N` fetches N tasks spread evenly over the planned order (for 2016-01..2026-08: `2019-06-b0017`
  and `2024-08-b0009`; N=6 adds 2017-04, 2021-05, 2023-01 and 2026-01). N is at most 20, because the pilot runs before
  any disk gate; without that bound, a pilot as large as the plan would fetch the whole span ungated. It writes
  `stock_bars_1min/pilot.json` with:
  - pages by Content-Encoding; wire bytes (as received: gzip bytes, or the identity JSON body) separately from stored
    and decoded bytes, each per page and per bar, and on-disk bytes per bar;
  - bars per page, the non-terminal page fullness, and pages against the ideal count;
  - quarantined bars (total and the largest per task) and the requested symbol-months without a bar (share and
    examples);
  - peak RSS (`getrusage`) and calls per minute.
- **Projection.** The disk projection is the larger of two scalings of the pilot's on-disk bytes (page files plus
  manifest rows): per planned task, and per bar with bars scaled by the universe's symbol-sessions. Calls are
  projected the same two ways from the pilot's pages and compared with D2's estimate: 172.4 bars per symbol-session
  (4.171e9 bars over the universe's 24,195,741 symbol-sessions for 2016-01..2026-09), per 10,000-bar page, plus one
  call per task. For 2016-01-01..2026-08-31 that is 425,763 calls.
- **Normalized-layer reserve.** X4 asks for total disk use, and D1's normalized minute layer (Zstd Parquet) is about
  70 GB for the span, measured at 16.8 bytes per bar in the D2 proposal. Every disk gate therefore keeps
  `normalized_reserve_bytes` (the projected bars times 16.8) free beyond the 20 GiB floor. For D2's 4.17e9 bars that is
  about 70 GB, so a raw backfill cannot leave too little room to normalize it.
- **Verdict.** The pilot weighs what the span still needs (the projection less the bytes already stored under this
  scope), so re-running it after a partial full run does not turn a passing pilot into a refusal.
  - `refused` (exit 2): that remainder exceeds 40% of free disk, or would leave less than the 20 GiB floor plus the
    normalized-layer reserve free (the lake shares its filesystem with the engine's state under `~/.local/state`), or
    the pilot returned no bars.
  - `overturn` (exit 4): one of D2's overturn conditions holds. Either non-terminal pages average under 95% full, or
    projected calls exceed 1.3x D2's estimate. D2 then switches to per-day tasks.
  - `incomplete` (exit 1): a pilot task failed. `pass` (exit 0) otherwise.
- **Full-run gate.** A full run (no `--pilot`) refuses unless `pilot.json` has the same scope fingerprint and verdict
  `pass`, and the remaining projection still fits 40% of current free disk and leaves the floor plus the reserve.
  Verdict `overturn` needs `--accept-pilot-flags REASON`, which is recorded in `pilot.json` (`acknowledged`); it never
  overrides a disk refusal. Pilot tasks count as completed tasks of the full run.
- **Disk while running.** Free disk is re-read before each task starts. A pilot or full run drains like `STOP` (exit
  3) when free space falls below the 20 GiB floor. A full run also drains when storing the remaining projection would
  leave less than the floor plus the reserve, or once its stored bytes exceed 1.5x the projection (the pilot
  under-sampled the span, for example 2020-2021, which neither 2-task pick samples).

## Commands

```sh
PY=<research runtime with DuckDB 1.5.5>          # universe build only
LAKE=<private lake directory outside the checkout>
$PY backfill.py universe --daily-dataset "$DAILY_DATASET" --out "$LAKE/universe-asof20260921.json"
python3 backfill.py stock_bars_1min --env-file "$PAPER_ENV_FILE" --out "$LAKE" \
    --universe "$LAKE/universe-asof20260921.json" --start 2016-01-01 --end 2026-08-31 \
    --rate 6000 --workers 16 --pilot 2
ECOSYSTEM_JOB_SECONDS=10800 ECOSYSTEM_JOB_MEMORY_HIGH=2G ECOSYSTEM_JOB_MEMORY_MAX=3G \
    "$ECOSYSTEM/bin/ecosystem-bounded-run" python3 backfill.py stock_bars_1min --env-file "$PAPER_ENV_FILE" \
    --out "$LAKE" --universe "$LAKE/universe-asof20260921.json" --start 2016-01-01 --end 2026-08-31 \
    --rate 6000 --workers 16
python3 backfill.py verify stock_bars_1min --out "$LAKE"
```

The full-run limits are estimates, not measurements:

- 10,800 s covers D2's 80-125 minutes. Raise it when the pilot's `projected_minutes_at_rate` (at the 6,000/min cap)
  times 1.5 exceeds it.
- The wrapper's defaults (600 s, 4G/6G) would stop the run. A stopped run resumes with the same command.
- Resident memory scales with `--workers`, not with completed tasks: at most `--workers` tasks are in flight and a
  task's row is dropped once its manifest line is written. Each worker holds one decoded page and its task's row,
  which is bounded (at most about 221 page entries and 100 quarantine entries). A synthetic full
  10,000-bar page measured about 1.1 MiB decoded and a 7 MiB peak while parsed (tracemalloc, 2026-09-24), so 16
  workers need on the order of 110 MiB for pages, beside the universe's 84 MB. The pilot's `peak_rss_mib` comes from
  at most N pilot tasks at once, not sixteen.

Exit codes: 0 done; 1 task failures or an incomplete pilot; 2 refused (before any request, or a pilot whose disk
projection does not fit); 3 stopped early by `STOP` or the disk re-check (resume with the same command); 4 the pilot
raised a D2 overturn flag. `touch "$LAKE/STOP"` drains a running pool: at most `--workers` tasks finish, the rest are
left for the next run, and the run exits 3. Remove `STOP` before the next run, which refuses while it exists. Ctrl-C
or a failed manifest append halts the run: no queued task starts and no in-flight task sends another page. `verify`
exits 0 only for a complete, intact dataset and 1 otherwise, so after the pilot it reports the planned tasks still
missing.

## Limits

- No provider request was made for `stock_bars_1min`. The acceptance is synthetic-fixture tests plus the local
  universe build. The pilot is the first native evidence for these points:
  - page fullness on month windows, which D2 never probed;
  - the gzip wire encoding on this endpoint;
  - the provider's handling of the nanosecond end bound. The security-identity capture sent the same form with
    HTTP 200 on daily bars.
- For renamed or reused tickers, `asof=2026-09-21` is only as good as the provider's symbol mapping (critique U11).
  The pilot's two tasks need not contain a renamed issuer. Spot-check one task holding `META` before 2022 against its
  daily bars.
- The disk figures are `statvfs` of the lake's filesystem. Under WSL2 that is the virtual disk's free space, which
  the Windows drive backing it may not have; on another PC check that drive too. The 20 GiB floor and the 1.5x
  overrun are review-chosen values (keep-but-compare), not measured ones. The normalized-layer reserve
  uses the D2 proposal's 16.8 bytes/bar, measured before `normalize.py` exists; it is kept free even once that layer
  is written, so a resume after normalization needs the reserve again.
- The news day end `23:59:59.999999999Z` follows the `/v1beta1/news` reference's nanosecond example; no news request
  has used it yet (the archive used `D+1 T00:00:00Z`).
- `symbols_without_bars` reports a requested symbol-month with daily sessions but no minute bar; it does not tell a
  mapping gap (critique U11) from a true absence. The pilot's two tasks need not contain a renamed issuer.
- `mover-early-entry/collect.py` (whose credential reader this tool reuses) still fetches with urllib's default,
  redirect-following opener; only its `credentials()` reader is used here.
- A task whose symbol list the provider rejects (HTTP 400) fails whole and is retried unchanged; there is no bisection.
  Every universe symbol came from accepted daily requests.
- The universe inherits the daily dataset's identity limits: 80 partial overlaps and 6 `identity_unresolved` pairs,
  and 235 undated ticker collisions.

## Checks

`python3 -m unittest tests.test_data_lake_backfill` runs synthetic openers and a fake clock, with no network (the
redirect tests patch urllib's HTTPS/HTTP handlers, so even the production opener opens no socket). The host lease and
the disk floor are patched for the whole module. The DuckDB test skips, and says so, in an interpreter without DuckDB;
the pinned engine venv has DuckDB 1.5.5 and runs it. It covers:

- the scope header's fields (including the planned tasks), and refusal of a changed span, code, universe or naming
  date; a refused full run writes no header;
- refusal of a header-less or edited header, a concurrent run, a second backfill on the host (another dataset or
  `--out`), a leftover `STOP`, and an `--out` inside a git work tree (a `.git` file or directory, a nested path, a
  symlink, the checkout itself, and the universe output);
- the client: redirects refused with no follow-up request and no retry, environment proxies ignored (against a stdlib
  control), 5xx/`URLError`/`HTTPException`/timeout retries, unexpected `Content-Encoding`, the 3,500 remaining floor,
  and a halted client sending nothing;
- the fingerprint on every row: a row naming another scope is fetched again and reported by `verify`, which also
  reports a missing or edited header on a page dataset;
- news paging, 429 back-off, resume, torn and malformed manifest lines, a missing or empty day file fetched again,
  fsync of day files, directories, header and manifest, the inclusive day bounds (a record stamped at midnight lands
  in one file), `STOP` draining with exit 3, Ctrl-C halting queued and in-flight work, and `verify` on a header-less
  news archive;
- page capture byte for byte: gzip and identity pages, token chain, hashes, DST windows, quarantine (counted, and
  listed up to 100), bars by symbol and symbols without bars, a failed task's clean retry, a repeated token and the
  page cap, an HTTP 429 and a 503 on a continuation page retried in place, fsync of pages, directories, header, pilot
  report and manifest, a missing or empty page file fetched again, a failed manifest append stopping all requests, and
  rows released once written;
- `verify` decoding pages: a row cut short, an edited next token, page count, bars by symbol or total; planned tasks
  without a row (a pilot-only lake is not complete, exit 1), a task outside the plan, a planned list that no longer
  matches the scope, a missing manifest and malformed rows reported rather than raised;
- universe membership, naming date, malformed input, and the DuckDB query on a tiny parquet;
- pilot selection, metrics and projection, identity pages and wire bytes, the 20-task pilot bound, the 40% refusal,
  the 20 GiB floor and the normalized-layer reserve, the remaining-bytes verdict after a partial run, the D2 overturn
  verdict (fullness and calls against D2's estimate) and its acknowledgement, the full-run gate, and the disk re-check
  draining a running pilot (floor) or full run (floor, reserve and 1.5x overrun);
- the command's exit codes: 0 done, 1 failed tasks or an incomplete pilot, 2 refused, 3 drained, 4 overturn;
- the rate cap, with a 6,000/min control that passes it.
