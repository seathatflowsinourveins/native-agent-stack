# Portable native token report

Capture the selected upstream counters into a private, append-only local ledger
and produce `manifest.json` plus a self-contained `manifest.html`. The reporter
reuses the accounting implementation exercised by this stack. It installs no
agent framework, client hooks, model route, service or scheduler.

Python 3.11+ is required. Node 24+ is needed for MCPorter; Node and the optional
`gpt-tokenizer` dependency are needed for exact artifact comparisons. Ordinary
counter capture uses the Python standard library and installed upstream tools.

## Install the selected upstream tools once

The [native recipes](../../recipes/README.md) contain the pinned release and
checksum procedure for RTK 0.50.0, plus the official upstream source links.
Keep a working existing installation; installation is not a step in each refresh.
For a new Linux x86_64 installation, the upstream commands are:

```sh
REPORT_TOOLS="${XDG_DATA_HOME:-$HOME/.local/share}/native-token-report"
mkdir -p "$REPORT_TOOLS/rtk-0.50.0"
gh release download v0.50.0 --repo rtk-ai/rtk \
  --pattern rtk-x86_64-unknown-linux-musl.tar.gz \
  --pattern checksums.txt --dir "$REPORT_TOOLS/rtk-0.50.0"
(
  set -eu
  cd "$REPORT_TOOLS/rtk-0.50.0"
  sha256sum --check --ignore-missing checksums.txt
  tar -xf rtk-x86_64-unknown-linux-musl.tar.gz
)
uv venv "$REPORT_TOOLS/headroom-0.37.0"
uv pip install --python "$REPORT_TOOLS/headroom-0.37.0/bin/python" headroom-ai==0.37.0
uv tool install jcodemunch-mcp==1.108.319
npm install --prefix "$REPORT_TOOLS/mcporter-0.14.1" mcporter@0.14.1
export PATH="$REPORT_TOOLS/rtk-0.50.0:$REPORT_TOOLS/headroom-0.37.0/bin:$REPORT_TOOLS/mcporter-0.14.1/node_modules/.bin:$HOME/.local/bin:$PATH"
```

The checksum command must report the selected archive as `OK`. Other operating
systems need their matching upstream release assets. The jcodemunch
[upstream installation guide](https://github.com/jgravelle/jcodemunch-mcp/tree/v1.108.319#install)
uses `uv tool install`; its dual-use license still applies. The reporter only
requests statistics and does not index code or invoke AI summarizers.

## Create one explicit configuration and refresh

Run from this repository. Select the project whose RTK subset you want to inspect
and a private state directory outside the checkout:

```sh
REPORT_PROJECT="$PWD"
REPORT_STATE="${XDG_STATE_HOME:-$HOME/.local/state}/native-token-report"
python3 tools/token-report/token_manifest.py init-config \
  --config "$REPORT_STATE/config.json" --state-dir "$REPORT_STATE" \
  --project "$REPORT_PROJECT" --rtk rtk --headroom headroom \
  --jcodemunch jcodemunch-mcp --mcporter mcporter
python3 tools/token-report/token_manifest.py refresh --config "$REPORT_STATE/config.json"
```

Open `$REPORT_STATE/manifest.html`. Subsequent sessions run only `refresh`.
Omit any tool flag you do not want to capture. The initializer refuses to overwrite
an existing configuration; edit that file to change the selected sources.
It points to the current checkout's catalog and stack. A later clone should create
its own configuration. [The example](config.example.json) shows the small schema;
its environment placeholders must be set and relative paths resolve beside that file.

The native calls are:

```sh
rtk gain --format json
rtk gain --project --format json
headroom savings --json
mcporter call --stdio "$(command -v jcodemunch-mcp)" \
  --env "CODE_INDEX_PATH=$HOME/.code-index" --env JCODEMUNCH_SHARE_SAVINGS=0 \
  --name jcodemunch --tool order \
  --args '{"action":"get_session_stats","args":{}}' --output json --no-oauth
```

jcodemunch 1.108.319 has a custom-index-root accounting mismatch: source retrieval
writes its native default savings ledger even when another index root is selected.
The initializer therefore uses the upstream default `.code-index` root. It does
not modify that root's configuration. Using its `counter` tool surface keeps six
resident MCP tools; changing the surface is separate from this reporter.

## Optional Context Mode snapshots

Add only the exact runtime stats roots you want to read:

```json
"context_roots": [
  {"name": "Chosen native client", "path": "/absolute/selected/runtime/sessions"}
]
```

The default reads the latest `stats-*.json` in each selected root and retains its
bytes. It does not inspect adjacent client configuration or session databases.
For an explicitly captured direct `ctx_stats` response, supply
`--context-stats-file /absolute/capture.json`; this displays that evidence separately.
There is no implicit search of Codex or Claude transcripts.

Historical event imports require explicit `rtk_database` or `headroom_events`
paths. An `rtk_database` path also enables RTK's client-visible view (see below).
`inspect_project_history` additionally queries retained RTK working directories;
`inspect_hook_history` additionally inspects the configured Context Mode roots'
hook metadata. Both default to false and are unnecessary for counters.

## Optional Loki provider-usage denominator (read-only)

Set `loki_url` (for example `"http://127.0.0.1:3100"`) to add a read-only
provider-usage reconciliation beside the counters above. Absent `loki_url`,
`refresh` runs exactly as before: no network call is attempted, and the
`loki_provider_usage` section of the JSON manifest (and the optional full
template, `token_manifest.full.html.in`; the smaller portable default template
has no Loki section) states `configured: false`.

When set, `refresh` issues one bounded `GET /loki/api/v1/query` (Loki's
documented instant-query endpoint) for the *last completed UTC calendar day*
(never the still-arriving current day), summing the `api_request` event's
`cache_read_tokens` field by its `query_source` label/attribute (see
[monitoring-usage](https://code.claude.com/docs/en/monitoring-usage) for both).
The response is grouped into:

- `by_query_source`: the raw per-source breakdown (nothing excluded);
- `total_all_sources`: their sum;
- `excluded_total`: the subset from `loki_excluded_query_sources` (default
  `["agent_summary"]` — that query_source is a summarization fork, not a
  session's own usage);
- `net_total`: `total_all_sources - excluded_total`.

This is a **usage denominator, not a savings counter**: it is never written to
this reporter's ledger and never summed with the RTK/Headroom/jCodeMunch/
Context Mode/TOON figures above, with another host's `net_total`, or across
days. A query or connection failure is recorded as an issue (`refresh` still
completes). Every refresh replaces the JSON manifest's `loki_provider_usage`
section wholesale (like every other section of `output_json`): a failed or
later refresh does not preserve an earlier successful reconciliation there.
The exact raw response and a request receipt (URL, LogQL query, requested
time, HTTP status, started/completed timestamps and an `artifact()` SHA-256 of
the body) are saved separately, under `captures/<run>/loki-provider-usage/`,
so the figures in any one refresh's manifest can always be traced back to the
literal bytes Loki returned for that refresh.

To compare `net_total` against the **`cacheReadTokens` value of the
`ccusage daily --timezone UTC -O -j` entry for that same UTC date** (or
another already-known transcript-based total for that same field), set
`loki_reference_totals`: a mapping of UTC `"YYYY-MM-DD"` date strings to
integers, one entry per day you have a reference figure for (the *last
completed UTC day* of each refresh, `loki_last_completed_day`, moves forward
daily, so a single undated reference would silently compare against the wrong
day once that day has passed). The matching reference command is
`ccusage daily --timezone UTC -O -j` for that same date (ccusage's own default
local-date grouping is not UTC; see the catalog's `--timezone UTC` usage
elsewhere). Optionally also set `loki_reference_label` and
`loki_reconciliation_tolerance_pct` (default `1.0`); both `loki_reference_totals`
and `loki_reconciliation_tolerance_pct` are validated up front, alongside
`loki_url` and `loki_excluded_query_sources`, so a malformed value is always a
configuration issue, never a same-day query failure. When today's window date
has no matching entry in `loki_reference_totals`, `reconciliation` reports
`{"status": "no reference for <date>", "window_date": ..., "timezone": "UTC",
"field": "cache_read_tokens", "available_dates": [...]}` instead of comparing
against a stale figure for a different day; a real comparison's `reconciliation`
also repeats `field` alongside `window_date` and `timezone`, so a saved manifest
names the compared field without cross-referencing `loki_provider_usage.field`.
This tool does not run `ccusage` or parse its output itself — only the
comparison arithmetic and the `within_tolerance` flag are computed here.

## Exact artifact comparisons

Install the pinned tokenizer only if you need retained-text comparisons:

```sh
npm install --prefix "$REPORT_TOOLS/tokenizer" gpt-tokenizer@3.4.0
```

Set `tokenizer_module` in the private configuration to the absolute path of
`$REPORT_TOOLS/tokenizer/node_modules/gpt-tokenizer/cjs/encoding/o200k_base.js`.
Then compare complete outputs for the same task:

```sh
python3 tools/token-report/token_manifest.py compare --config "$REPORT_STATE/config.json" \
  --tool selected-tool --before /absolute/baseline.txt --after /absolute/candidate.txt \
  --boundary "Same retrieval task; required source fields checked against the original"
python3 tools/token-report/token_manifest.py refresh --config "$REPORT_STATE/config.json"
```

The command preserves immutable UTF-8 inputs and their SHA-256 hashes, counts
both complete artifacts, and deduplicates the same tool/input/output/tokenizer/
boundary combination. Expansion remains negative. The boundary describes your
quality check; the reporter does not infer semantic equivalence. An optional
`toon` executable enables the existing strict catalog roundtrip and exact
comparison against compact JSON, with that result stored separately.

## Read the numbers correctly

- RTK global and project snapshots overlap. The report never sums them.
- RTK's total is uncapped. Each row saves `max(0, raw - filtered)`, with both
  sides in `ceil(bytes/4)`, so a few very large outputs can dominate the total.
  Rows where filtering made the output longer count as 0.
- When `rtk_database` is configured, the global snapshot adds `client_visible`,
  which re-counts every row as a client first shows the output:
  - whole up to `client_inline_chars` (default 30000, allowed 4000–128000);
  - otherwise a preview of at most `client_preview_chars` (default 2000, which
    must stay below the inline limit).

  Those defaults are Claude Code 2.1.282's `bashOutputMaxChars` and its
  saved-output preview. The boundary text says "by default" only when both
  limits are the defaults.
  - **Sign:** the view keeps the sign, so an expansion, or a filtered output
    longer than the raw output's preview, counts as `added`. Its net therefore
    differs from the floored upstream total.
  - **It is a model, not a bound:**
    - bytes stand in for characters, which is exact only for ASCII;
    - the preview's wrapper text and later reads of saved output files are not
      counted;
    - rows from scripts that no client displayed are included;
    - Codex has its own output limits.
  - **Mismatch check:** if the configured database holds more than 1% fewer rows
    than `rtk gain` reported, the view is omitted and an issue names the
    mismatch. The 1% allows for retention pruning between the two reads.
- Headroom 0.37.0 calls a 30-day estimate `lifetime`, and
  `headroom savings --json` also prints zero when its ledger file does not
  exist. When the report names its ledger path, the snapshot records
  `ledger_present`. It resolves a relative path from the configured project, the
  directory Headroom runs in, so an absent ledger is not read as a measured zero.
- Context Mode 1.0.169 uses retained-event and byte estimates with finite
  retention. Its `tokens_saved_lifetime` is retained events × 256.
- jcodemunch's persistent total estimates bytes avoided divided by four and can
  include repeated verification reads. Its schema-size estimate is a separate field.
- Exact artifact counts use `o200k_base`; they are not provider billing or measured
  causal lifetime savings. Imported provider studies retain their original scope.
- `loki_provider_usage` is a **usage denominator, not a savings counter**: it
  measures the prior day's `api_request` volume, so never add it to the
  RTK/Headroom/jCodeMunch/Context Mode/TOON figures above, to another host's
  `net_total`, or across days. `excluded_total` (default: `agent_summary`) is
  subtracted before `net_total` for the same reason a transcript-based total
  excludes summarization forks; `total_all_sources` keeps every `query_source`.

Each refresh saves complete command output, exits and hashes under `captures/`.
Native failures return a nonzero reporter exit while still writing the report;
the last good observation remains separate. Keep local config, raw reports and
the ledger private. Publish only a separately reviewed sanitized receipt.

## Attach actual native runs and dashboard results

Add `returned_results_json` to the private configuration to select one explicit
evidence manifest. The native commands run separately; importing this manifest
does not execute commands, browse dashboards or repeat provider work.

```json
{
  "schema_version": 1,
  "captured_at": "2026-09-21T00:00:00Z",
  "scope": "Example schema only; replace with actual selected observations",
  "records": [
    {
      "id": "chosen-native-operation",
      "runtime": "Selected native client",
      "component_ids": ["rtk"],
      "kind": "upstream native operation",
      "command": {"argv": ["rtk", "gain", "--format", "json"]},
      "started_at": null,
      "completed_at": null,
      "status": "not executed in this example",
      "observation": "Supply the actual returned result and observation",
      "boundary": "No execution or savings is established by this schema example",
      "attachments": []
    }
  ]
}
```

Each selected attachment requires `label`, `path`, `bytes` and `sha256`, with an
optional `mime_type`. Relative file paths resolve beside this evidence manifest.
Tool invocations can use `command: {"tool": "name", "arguments": {}}` instead of
argv. Preserve execution dates, failures, original stream hashes and the scope of
any selected projection. Select safe returned outputs; do not attach authentication
stores or unrestricted transcripts. Public receipts require a separate review.

The loader checks each complete file against its declared size and SHA-256, copies
it into the private capture, and embeds exact base64 bytes with a UTF-8 preview
when possible. Limits are 2 MiB per attachment and 16 MiB total. Missing, modified
or malformed sources produce a visible issue without substituting old success.
The source manifest remains retained for diagnosis.

Both templates expose these records and real browser downloads. Full JSON export
contains the same attachments. The optional full local view is selected with
`html_template` pointing to `token_manifest.full.html.in`; keep the adjacent
`returned_results.js` with the reporter. The smaller portable template remains the
default. This presentation is local integration code, not an upstream dashboard.

The attached-results view joins every selected component to its observations,
shows missing coverage, and filters by component and runtime together. Historical
aliases are normalized for display while downloads retain the original records.
Coverage counts include failures and dated observations; they are not E2E pass
counts. Explicit PNG, JPEG and WebP attachments render inline from their verified
bytes, with lossless downloads; SVG and other files remain download-only.

For an existing ledger, optional `counter_scopes` keys `rtk_global`, `rtk_project`
and `headroom` preserve its original scope strings when upgrading the reporter.
Explicit `inspect_project_history` and `inspect_hook_history` preserve previously
chosen inspection behavior; a fresh configuration defaults them off. Refreshing
the report must not create renamed duplicates of existing counters.

## Verify the bundle

```sh
python3 -m unittest discover -s tools/token-report -p 'test_*.py' -v
node --test tools/token-report/test_returned_results.cjs
python3 scripts/validate.py
```

The tests cover empty-host operation, explicit Context Mode scope, bad counters,
failed refreshes, overlapping views, counter resets, exact evidence identity,
duplicate imports and negative artifact deltas. They do not require native accounts.
