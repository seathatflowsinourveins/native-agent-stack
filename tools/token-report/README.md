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

## Optional scheduled refresh

The reporter itself still installs no scheduler (see the top of this page); a
separate, opt-in pair of drafted systemd `--user` templates can call `refresh`
on a schedule instead of by hand:
[`token-report-refresh.service`](../../adoption/templates/systemd/token-report-refresh.service)
and [`.timer`](../../adoption/templates/systemd/token-report-refresh.timer). Like
this repository's other drafted units
(`adoption/templates/systemd/codex-broker-reaper.{service,timer}`), no host has
loaded, started or enabled either one; the coordinator installs them after
review, substituting `@REPOSITORY@` (this checkout's path) and
`@REPORT_CONFIG@` (the `--config` path from "Create one explicit configuration
and refresh" above) first.

Before installing, give that configuration's `"rtk"`, `"headroom"` and, if
set, `"toon"` keys absolute installed paths (for example by passing
`--rtk "$REPORT_TOOLS/rtk-0.50.0/rtk" --headroom "$REPORT_TOOLS/headroom-0.37.0/bin/headroom"`
at `init-config` time, or by editing an existing config.json directly).
`initialize_config` stores those fields verbatim, unlike `jcodemunch`/
`mcporter`, which it resolves once with `shutil.which()` at init time, so a
bare name such as this page's own interactive-shell example
(`--rtk rtk --headroom headroom`) only resolves through that shell's exported
`PATH` and would fail under a systemd `--user` manager's own minimal `PATH`.
There is no `--toon` flag at `init-config` time (see "Exact artifact
comparisons" below): give it an absolute path the same way, directly in an
existing config.json.

Two more prerequisites apply to whatever actually *runs* this service, not
just the shell used to install it. `ExecStart=` pins `/usr/bin/python3`
directly, so that exact interpreter must itself satisfy "Python 3.11+ is
required" above, regardless of any other `python3` a shell's `PATH` might
resolve. Node is different: `mcporter` and the optional `toon` executable
(see "Exact artifact comparisons" below) are each a `#!/usr/bin/env node`
script, and while `initialize_config` resolves the configured `--mcporter`
value to an absolute path once with `shutil.which()` at `init-config` time
-- there is no matching `--toon` flag, so give `"toon"` an absolute path
directly in an existing config.json instead, the same way as `"rtk"`/
`"headroom"` above -- running either resolved absolute path still makes
`env` re-resolve `node` through *the executing process's own* `PATH`, not
the shell `init-config` ran in. When this configuration selects
jcodemunch/mcporter capture or sets `"toon"`, confirm a qualifying `node`
already resolves under `systemctl --user show-environment` before
installing (`mcporter`'s own `package.json` requires `>=24`; the installed
`@toon-format/cli` sets no `engines.node` floor of its own, but its
`bin/toon.mjs` still needs a working `node` to run that same kind of
shebang). A `node` exported only by an interactive shell's `nvm`/`fnm`
rc-file init, or otherwise missing from the manager's typically minimal
`PATH`, makes just that one capture report an issue: the refresh itself
still completes and the reporter exits nonzero, but with `"toon"`
configured specifically, that means *every* scheduled run hits this and
exits nonzero, since `refresh` treats any issue as a failed run. If needed,
prepend a qualifying `node`'s directory to the manager's own full `PATH` --
read the existing value first with `systemctl --user show-environment` --
in an explicit `Environment=PATH=...` line on the installed unit;
*replacing* the whole `PATH` instead of prepending to it would also change
what any other bare-name command in the unit resolves to (the unit's
`ExecCondition=` calls `/bin/date` by absolute path for exactly this
reason, so it is unaffected either way). Setting an absolute `"node"` key
directly in config.json (parallel to `"rtk"`/`"headroom"`/`"toon"`) only
covers this reporter's own internal tokenizer-count invocation used while
comparing `toon` output; it does not change what `"toon"`'s own `env node`
shebang above resolves at run time.

The timer's four fixed local times a day (03:15, 10:15, 16:15, 22:15) never
land inside the Sat/Sun 05:00-09:00 quiet window on any on-schedule fire
(checked with `systemd-analyze calendar`), and `systemd-analyze --user verify`
passes on both files. A calendar timer can still catch up on a missed tick
immediately after the host resumes from sleep, per `man systemd.timer`. When
that resume lands on a Saturday or Sunday between 05:00 and 09:00, the
service's own `ExecCondition=` re-checks the real clock at run time and skips
that one run instead of executing it, without marking the unit failed; a
Monday-Friday resume in that same clock window is not a quiet window and
still runs the refresh normally. See both unit files' own comments for the
exact verified source lines and command output this rests on. The service
sets `HEADROOM_UPDATE_CHECK=off`, `HEADROOM_OFFLINE=1`
and `DO_NOT_TRACK=1` so a scheduled run's one Headroom call
(`headroom savings --json`) never makes a network call; that call is
otherwise a pure read against the shared `~/.headroom` state (no
`HEADROOM_WORKSPACE_DIR` redirect is needed or set), which is what the
dashboard row for it is supposed to reflect.

Installing the timer also means the [native dashboard adapter](../../observability/native-data/README.md)
sees a fresh `refresh` only every few hours instead of on an unpredictable
manual cadence. Its own `stale_after_seconds` (a key in that adapter's
private config, schema in
[`config.example.json`](../../observability/native-data/config.example.json),
bounds 1-86400 enforced in `observability/native-data/snapshot.py`, default
1800) is shorter than the timer's largest gap between two runs (7 hours =
25200 seconds) and would otherwise mark the token-report row stale between
ticks. Raise it to 28800 (8 hours) by hand in that private file when the
timer is installed: comfortably above the 7-hour gap plus the service's
`TimeoutStartSec=900` margin, while still catching a scheduler that has
actually stopped well inside a day. This reporter does not read or write
that adapter's config; nothing here changes it automatically.

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
