# Data lake: governed historical backfill (source layer)

`backfill.py` fills the lake's raw source layer from Alpaca's historical REST API under a shared token bucket
(`--rate`, at most 6,000 requests/min so the live monitor, scans and the engine keep headroom under the account's
10,000/min data limit, measured 2026-09-24), with HTTP 429 back-off to the limit's reset. GET only; the data stays
private (licensed market data and news) in an operator-chosen `--out` directory outside the checkout. The design
follows the 2026-09-24 data-and-execution convergence record (D1 lake architecture, D2 minute bars; backlog items
7-8) and its completeness critique (X2-X4). Normalized Zstd Parquet is a separate, later layer.

## Scope header: a changed scope never resumes

Every dataset directory `<out>/<dataset>/` carries `scope.json`, which the first run writes before any request:

| Field | Meaning |
| --- | --- |
| `code_sha256` | sha256 of the `backfill.py` that collects the dataset |
| `endpoint` | host and path |
| `fixed_params` | every constant request parameter; for `stock_bars_1min` including the universe's `asof` |
| `symbols_sha256` | sha256 of the planned task list (each task id with its symbols); `null` for `news`, which is not symbol-scoped |
| `span` | the requested `--start` and `--end` |
| `task`, `capture` | task unit (batch size, New York session window) and raw capture mode |

`fingerprint` is the sha256 of that scope; `provenance` (creation time, universe file and source hashes) is recorded
beside it but is not part of it. Every page-capture manifest row repeats the fingerprint as `scope_fingerprint` (D1:
each task carries its scope fingerprint). A row naming another fingerprint never counts as done, so its task is fetched
again, and `verify` reports it. Each of these is refused with exit 2 before any request:

- a run whose scope differs in any field;
- a header that no longer hashes to its fingerprint;
- a manifest without a header, which was collected before headers existed. This directory is left untouched.

Collect a new scope, a new code version or an extended span into a new `--out` directory. This is the rule
`broad-universe/collect_daily.py` already applies. A lock file (`.lock`, `flock`) refuses a second concurrent run on
the same dataset.

## Datasets

| Dataset | Endpoint and fixed parameters | Task | Raw capture | Status |
| --- | --- | --- | --- | --- |
| `news` | `/v1beta1/news` (Benzinga via Alpaca), `include_content=true`, 50 per page, ascending | one UTC calendar day | records | Backfilled 2015-01-01..2026-09-23 on 2026-09-24: the manifest holds 4,284 days, 2,217,343 records and 46,650 pages (private; about 1.1 GB). Two runs wrote it: 2026-09-14..20 first (7 days, 3,910 records, 82 pages), then the other 4,277 days (2,213,433 records, 46,568 requests, 0 HTTP 429, 0 failed days, about 947 s at `--rate 3000 --workers 8`) |
| `stock_bars_1min` | `/v2/stocks/bars`, `timeframe=1Min`, `feed=sip`, `adjustment=raw`, `limit=10000`, `sort=asc`, `asof` = the universe's naming date (2026-09-21) | 100 symbols x one calendar month, from 04:00 ET on the first day to 19:59:59.999999999 ET on the last | wire pages | Code and synthetic tests only; not yet run against the provider |

### news: kept as collected (record capture)

- Each day file `news/<YYYY>/<MM>/<DD>.jsonl.gz` holds that day's records re-serialized with sorted keys (gzip, fixed
  mtime). These are not the wire pages.
- Each manifest row covers one day: records, pages, the day file's sha256, bytes and fetch time. Rows carry no request
  parameters and no code sha. The task is held in memory until the day is complete.
- The 2015-2026 archive predates scope headers. It has no `scope.json`, so a news run into that directory is refused.
  - Its operator-written `run-header.json` records code sha256 `1119c92b…`, which is the committed `backfill.py` at
    `1d52ed21`, and the fixed parameters. Its `result` block pairs the archive's 4,284 days with the second run's
    record and request counts; the manifest totals above are the archive's.
  - `backfill.py verify news` re-hashed all 4,284 day files against the manifest on 2026-09-24 with 0 problems
    (local integration, read-only).
  - The archive is complete and needs no resume. An incremental pull goes into a new `--out` with its own header.
- `updated_at` changes after publication are not re-fetched. The live monitor records receive times going forward,
  and D5 normalizes revision timing.

### stock_bars_1min: page capture

- **Requests.** Every page is requested with `Accept-Encoding: gzip`.
- **Storage.** Each page is written as it arrives to `stock_bars_1min/<YYYY>/<MM>/b<NNNN>/p<NNNNN>.json.gz`, so memory
  stays bounded per page.
  - A gzip-encoded page is stored byte for byte as the wire delivered it.
  - An identity-encoded page is gzip-wrapped (fixed mtime) and labelled `content_encoding: identity`.
- **Manifest row per task.** Each row records:
  - the task's base request parameters;
  - per page: its `page_token`, file, `sha256` of the stored bytes, `json_sha256` of the decoded body, sizes, bar
    count, whether a next token followed, and fetch time;
  - the bar total;
  - symbols the provider returned that were not requested;
  - the quarantine list.
- **Quarantine.** Bars stamped outside 04:00-20:00 New York time (for example a print stamped exactly 20:00 ET inside
  the month) are listed as quarantined, not dropped, and the task still completes. The raw pages stay immutable, and
  the normalized layer excludes these bars.
- **Failures.** A task is recorded only when its page chain reaches a null `next_page_token`.
  - An interrupted attempt's pages sit in `b<NNNN>.part/` and are replaced when the task is fetched again.
  - A failed task is listed in the run result and retried on the next run of the same scope.
  - A page chain that repeats a token or passes 2,000 pages fails its task.
- **Verification.** `verify` re-hashes every page and checks:
  - that the scope header is present and intact;
  - that every row names the header's fingerprint;
  - that each chain runs from no token to a null next token;
  - that page bars sum to the task total.

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
  and `2024-08-b0009`). N is at most 20, because the pilot runs before any disk gate; without that bound, a pilot as
  large as the plan would fetch the whole span ungated. It writes `stock_bars_1min/pilot.json` with:
  - raw (wire) bytes per page, decoded bytes per page, raw and on-disk bytes per bar;
  - bars per page, the non-terminal page fullness, and pages against the ideal count;
  - peak RSS (`getrusage`) and calls per minute.
- **Projection.** The disk projection is the larger of two scalings of the pilot's on-disk bytes (page files plus
  manifest rows):
  - per planned task;
  - per bar, with bars scaled by the universe's symbol-sessions.
- **Verdict.** The verdict is `pass` when the projection is at most 40% of free disk. Otherwise it is `refused`
  (exit 2), or `incomplete` if a pilot task failed.
- **Flags.** D2's overturn conditions are reported as flags: pages under 95% full, or more than 1.3x the ideal calls.
  Either means per-day tasks should replace month tasks.
- **Full-run gate.** A full run (no `--pilot`) refuses unless `pilot.json` has the same scope fingerprint and verdict
  `pass`, and the remaining projection still fits 40% of current free disk. Pilot tasks count as completed tasks of
  the full run.

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
- The 2G/3G memory limits assume a small resident set: the universe loads in 84 MB and each worker holds one page.
  Confirm them against the pilot's `peak_rss_mib`. That figure comes from two concurrent tasks, not sixteen.

Exit codes: 0 done, 1 task failures or an incomplete pilot, 2 refused. `touch "$LAKE/STOP"` drains a running pool;
tasks not started are left for the next run.

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
- The disk gate is checked when a run starts, against the pilot's projection. Nothing checks free space while the
  run is going. A run can exhaust the disk only by writing more than 2.5 times the largest projection the gate admits,
  for example if the two pilot tasks badly under-sample the 2020-2021 minute-bar density.
- A task whose symbol list the provider rejects (HTTP 400) fails whole and is retried unchanged; there is no bisection.
  Every universe symbol came from accepted daily requests.
- The universe inherits the daily dataset's identity limits: 80 partial overlaps and 6 `identity_unresolved` pairs,
  and 235 undated ticker collisions.

## Checks

`python3 -m unittest tests.test_data_lake_backfill` runs synthetic openers and a fake clock, with no network. It
covers:

- the scope header's fields, and refusal of a changed span, code, universe or naming date;
- refusal of a header-less or edited header, and of a concurrent run;
- the fingerprint on every row: a row naming another scope is fetched again and reported by `verify`, which also
  reports a missing or edited header on a page dataset;
- news paging, 429 back-off, resume, torn manifest line and STOP, and `verify` on a header-less news archive;
- page capture byte for byte: gzip and identity pages, token chain, hashes, DST windows, quarantine, a failed task's
  clean retry, and tamper detection by `verify`;
- universe membership, naming date and malformed input;
- pilot selection, metrics and projection, the 20-task pilot bound, the 40% refusal and the full-run gate;
- the rate cap, with a 6,000/min control that passes it.
