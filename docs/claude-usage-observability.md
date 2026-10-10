# Claude usage in Lanes

The **Claude usage** row in `/d/cc-lanes` shows the last observed Max-plan
`five_hour` and `seven_day` fractions and reset times, followed by each API key's
ledger charges against its $200 edge. Each panel links to
[OmniRoute's GPT-pool dashboard](http://127.0.0.1:21128/dashboard/analytics).
Subscription limits, API ledger charges, request tokens and API-equivalent OTel
cost are separate measures. Reset timestamps display in UTC.

`observability/claude_usage_metrics.py` reads CC-owned stream captures and the
api-actions ledger, then publishes a node_exporter textfile using the official
`prometheus-client==0.26.0` serializer and atomic writer. It accepts named files
only. It does not launch Claude, import the Agent SDK, discover accounts, read
credentials or load user configuration. The lane's tests use synthetic data.
Live sampling, collector installation and dashboard provisioning belong to the CC
after landing; this change does not claim host deployment or live coverage.
`observability/claude_usage_sampler.py` now supplies the CC-owned fenced
acquisition entry point, using only the allowlisted event fields and explicit
non-secret identity files. Lanes run it solely against isolated stub clients
and synthetic identities.

## CC installation after landing

The PR ships files under `observability/claude-usage/`; it installs nothing.
Prepare one private regular identifier file (mode 0600) per pooled account,
outside its existing authenticated Claude runtime directory. Each contains one
non-secret stable identifier line. Fill `accounts.json` from
`accounts.json.example`: `identity_file` and `config_dir` are absolute paths.
The latter selects the CC-owned native runtime through `CLAUDE_CONFIG_DIR`;
the sampler does not inspect its credentials or settings.

Identifiers are SHA-256 hashed in process and discarded. A persistent
hash-to-`acct-N` registry supplies stable opaque labels even if the pool grows
or identity file paths change. No identifier, filename, email, organization,
prompt or response reaches metrics, state or sampler logs. Retain
`sampler.json` between runs. Do not supply a credential or account cache as an
identifier file.

The CC installs the isolated Python runtime with:

```sh
sh observability/claude-usage/install-runtime.sh \
  "$HOME/.local/share/native-agent-stack/claude-usage-runtime"
```

The script uses upstream `venv` and pip `--require-hashes --only-binary=:all:`
with `observability/claude-usage/requirements.txt`, the official client wheel
hash also included by CI. It copies the two entry points but does not install
or start units, create accounts, change authentication or read settings.

After preparing the account paths, the CC installs these user-unit files:

- `claude-usage.service`: hash-locked Python runtime, protected probe directory,
  named ledger/state/output paths, no retries and bounded oneshot timeout.
- `claude-usage.timer`: UTC `00,15,30,45` calendar; no persistent catch-up.
- `claude-usage-node-exporter.service`: node_exporter on `127.0.0.1:29101`, with
  only the textfile collector enabled. Existing hostmetrics remain independent.

The CC supplies the pinned upstream node_exporter binary and merges the shipped
`prometheus-scrape.yaml` job into the existing Prometheus config. Validate that
config with upstream `promtool check config`. The node_exporter textfile flag
matches the sampler output directory. Reloading/enabling/starting the units
and Grafana provisioning belong to the CC after landing.

## CC sampling contract

Use the one-word probe from the CC's `cc-native-practice-20261009/w5_guard.py`,
with its fenced flags:

```text
claude -p "Reply with the single word ok." --tools "" --strict-mcp-config \
  --setting-sources local --permission-mode dontAsk --max-turns 1 \
  --max-budget-usd 0.2 --output-format stream-json --verbose --no-session-persistence
```

The sampler requires a private probe working directory with no
`.claude/settings.local.json` in it or any ancestor, including dangling
symlinks. It checks metadata only and refuses before launching if the fence
fails; it never reads those settings. The client receives an allowlist of
ordinary runtime variables plus `CLAUDE_CONFIG_DIR`. API-key, OAuth-token,
parent-session and telemetry environment values are not read/copied. Native
stderr is discarded and only numeric/status event fields are retained from
stdout. The 180-second timeout and native session-persistence suppression
bound each probe. Lanes never run this command against a real client/account.

Run at most once per account per 900 seconds, with a single CC-owned scheduler
and an attempt-time guard shared across retries. A 15-minute calendar such as
`*-*-* *:00,15,30,45:00 UTC`, without catch-up or immediate retries, is shipped.
An exclusive persistent lock covers identity-index assignment, attempts and
collection. Actual launch time is saved durably before each account's probe,
so a crash, timeout, restarted invocation, overlapping timer or clock rollback
cannot bypass the 900-second guard. A pass supports at most eight accounts.
Valid rejection events are retained even when the native client exits nonzero.
Failed attempts export failure metrics without raw output. Captures are
atomically replaced with their actual observation mtime; replayed old data
does not refresh its age. The adapter itself does not invoke or retry probes.

Native stream events have `type: rate_limit_event`, a `rate_limit_info` object,
`status` (`allowed`, `allowed_warning`, `rejected`) and optional camelCase fields
`rateLimitType`, `utilization`, `resetsAt`. Utilization is a **0–1 fraction**;
reset time is Unix **seconds**. The adapter also accepts the reference's
`rate_limit_info.unifiedWindows` recording shape. Native statusline
`used_percentage` (0–100) is a different contract and is not accepted here.

These are transition events, not complete account snapshots. A missing window
or utilization remains unknown. A later event without utilization preserves
the prior nonexhausted value and its original observation time. Replaying an older capture
cannot replace newer observations. Reset observation age is tracked separately.
The bars and reset panels hide fields older than 30 minutes; the observation-age
panel still exposes the age of retained stale values. An explicit allowed
recovery without numeric utilization clears the previous rejection to UNKNOWN.

A rejected named window is always **1.0**, even when native utilization is
missing or zero. Numeric exhaustion is capped at 1.0. A rejection without a
supported window marks otherwise unknown windows assumed 1.0 and exports
`claude_max_rejection_assumed=1`; it cannot overwrite a confirmed allowed
window in the capture or a retained unexpired observation. The bar legends
distinguish measured and assumed data. No reset time is invented. When a known
reset passes, older utilization clears to UNKNOWN, never a recovered zero;
replaying the old capture cannot resurrect it. A newer allowed observation
survives the old reset. Malformed values and JSON increase a bounded error
count; missing sources do not become zeros.

Separate account status and capture age panels retain every configured account
as MEASURED, ASSUMED 100%, STALE or UNKNOWN. They use capture success, per-account
errors, window presence, rejection markers and timestamps. Failed or never
observed accounts remain UNKNOWN; an observation/source older than 30 minutes
is STALE. The inventory query retains account rows for seven days if the
sampler stops, matching host retention. Beyond retained history, inventory
itself is unknown. A bounded input-error panel also shows capture/ledger health.

## Collect recorded data

Use the hash-locked runtime installed above, or install the shared runtime
requirements with pip's hash enforcement into a dedicated interpreter. The CLI explicitly
names every account capture; repeat `--capture` for the pool:

```sh
/path/to/hash-locked-runtime/bin/python observability/claude_usage_metrics.py \
  --capture acct-1=/path/to/recorded/acct-1.jsonl \
  --capture acct-2=/path/to/recorded/acct-2.jsonl \
  --ledger /path/to/api-actions-20261008/api-actions-ledger.jsonl \
  --state /path/to/claude-usage/state.json \
  --output /path/to/node-textfiles/claude-usage.prom
```

The authorized ledger lives under the native-agent-stack coordination state,
in `api-actions-20261008/api-actions-ledger.jsonl`. Its `key` column is a
**non-secret alias**, never credential material. The adapter hashes aliases
immediately and persists only a full SHA-256-to-`key-N` registry. Keep the state
file between runs so indexes survive pool growth. State also contains only
numeric per-window observations; captures, references, workloads and arbitrary
ledger metadata are not persisted. Account indexes must already be opaque.

Match the producer's original-debit attribution: a settlement belongs to the
debit's key even after a key switch. `actual_usd` on settle/void rows contributes
to ledger charges, including signed reconciliation credits; `max_usd` on open
debits contributes to pending reservations.
An `outcome: unknown` settlement keeps its full reservation as accounted charges
until reconciliation; the uncertain metric is a **subset**, not an extra charge.
Provider snapshots and notes add no charges. A malformed financial row makes
the whole API observation unknown rather than publishing a partial total.

Legacy rows without a key stay in the unattributed metrics and receive no
per-key $200 denominator. Once the CC confirms the producer's non-secret
`DEFAULT_KEY` alias, supply it with `--legacy-key-alias`; the exporter then
attributes those rows consistently with the producer. Never infer that alias
from an email, a credential or a provider-console balance. The $200 edge follows
this task's display contract; it is not an additional debit authorization.

Configure upstream node_exporter with
`--collector.textfile.directory=/path/to/node-textfiles`, restricted to the
collector's data directory, and scrape its loopback endpoint from Prometheus.
Use one exporter instance for the pool; the dashboard's opaque indexes refer to
that host's registry. Confirm node_exporter's `node_textfile_scrape_error` is
zero and that the existing `ns2604-prometheus` datasource receives the samples.
The native textfile collector ignores temporary files and does not accept
sample timestamps: reset, capture and observation times are gauge **values**.
The official writer atomically replaces the final `.prom` file. State is locked
across adapter invocations and saved before publishing its assigned key indexes.

## Metrics and dashboard

| Metrics | Labels | Meaning |
| --- | --- | --- |
| `claude_max_utilization_ratio`, `claude_max_observed_timestamp_seconds` | `account`, `window` | Last numeric utilization and its source observation time |
| `claude_max_reset_timestamp_seconds`, `claude_max_reset_observed_timestamp_seconds` | `account`, `window` | Native reset time and independent observation time |
| `claude_max_rejection_assumed` | `account`, `window` | Conservative fallback for a rejection without a supported scope |
| `claude_max_capture_timestamp_seconds`, `claude_max_capture_success` | `account` | Capture mtime and presence of a valid rate-limit event |
| `claude_max_account_present`, `claude_max_window_present` | `account`, `window` | Configured inventory and presence of a numeric observation before its reset |
| `claude_max_input_errors` | `account` | Bounded per-account capture/sampler errors |
| `claude_api_spend_usd`, `claude_api_pending_usd`, `claude_api_uncertain_usd`, `claude_api_edge_usd` | `key` | Ledger charges, open reservations, uncertain subset and $200 edge |
| `claude_api_unattributed_{spend,pending,uncertain}_usd` | none | Financial rows without confirmed key attribution |
| `claude_usage_collection_timestamp_seconds`, `claude_usage_ledger_success` | none | Adapter freshness and complete ledger parsing health |
| `claude_usage_input_errors` | bounded `source` (`capture`, `ledger`) | Input errors in this collection; no raw errors or source text |

No other labels, default Python/process collectors, identity fields, prompt
text or response text are registered. Diagnostics use a fixed error class.
Captured data and numeric state remain outside the repository. On corrupt state
or publication failure the CLI exits 1 without overwriting the previous final
textfile; dashboard freshness gates age that observation out.

`observability/lanes_dashboard.py` builds the row and preserves existing panel
IDs. Grafana fraction bars use `percentunit`, min 0/max 1 and instant Prometheus
queries. Reset panels multiply seconds by 1000 for `dateTimeAsIso`; dashboard
timezone is UTC. API queries
require a successful complete ledger collection, and usage/spend panels expire
when collection is older than 30 minutes. No query supplies an artificial zero.
Generate and check the committed dashboard through the normal builder:

```sh
python3 observability/ns2604_dashboards.py
python3 observability/ns2604_dashboards.py --check
python3 -m unittest tests.test_claude_usage_metrics tests.test_claude_usage_sampler tests.test_ns2604_dashboards -v
python3 scripts/validate.py
```

The unit-test interpreter must have CI dependencies installed. The native
query test additionally uses upstream `promtool` from PATH or the
`CLAUDE_USAGE_PROMTOOL` environment variable. Its synthetic series prove that
the real five-hour bar query returns exhausted-account 1.0, excludes a stale
account, retains failed/stale/never-observed account status, marks assumed
versus measured data, converts reset seconds to milliseconds, and expires API data when
collection stops. This optional native-tool test does not launch a probe.
Parser, CLI and stub-sampler contracts run without that tool. Unit/configuration
checks do not install or start services.
The source selection, version pins and reproduced boundaries are recorded in
[the decision record](decisions/2026-10-10-claude-usage-observability.md).
