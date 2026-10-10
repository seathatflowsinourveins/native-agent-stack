# Claude usage in Lanes

The **Claude usage** row in `/d/cc-lanes` shows the last observed Max-plan
`five_hour` and `seven_day` fractions and reset times, followed by each API key's
ledger charges against its $200 edge. Each panel links to
[OmniRoute's GPT-pool dashboard](http://127.0.0.1:21128/dashboard/analytics).
Subscription limits, API ledger charges, request tokens and API-equivalent OTel
cost are separate measures.

`observability/claude_usage_metrics.py` reads CC-owned stream captures and the
api-actions ledger, then publishes a node_exporter textfile using the official
`prometheus-client==0.26.0` serializer and atomic writer. It accepts named files
only. It does not launch Claude, import the Agent SDK, discover accounts, read
credentials or load user configuration. The lane's tests use synthetic data.
Live sampling, collector installation and dashboard provisioning belong to the CC
after landing; this change does not claim host deployment or live coverage.

## CC sampling contract

Use the one-word probe from the CC's `cc-native-practice-20261009/w5_guard.py`,
with its fenced flags:

```text
claude -p "Reply with the single word ok." --tools "" --strict-mcp-config \
  --setting-sources local --permission-mode dontAsk --max-turns 1 \
  --max-budget-usd 0.2 --output-format stream-json --verbose
```

The CC runs it in its designated probe working directory, with a 180-second
timeout and `CLAUDECODE` removed from the inherited environment, as in the
reference. Lanes never run this command. The CC owns account selection through
its existing authenticated runtime; the adapter receives an opaque index only.
Keep the hash-to-slot mapping outside the metrics and use stable `acct-1`,
`acct-2`, ... indexes. Do not pass emails, organization names or credentials as
account arguments.

Run at most once per account per 900 seconds, with a single CC-owned scheduler
and an attempt-time guard shared across retries. A 15-minute calendar such as
`*-*-* *:00,15,30,45:00`, without catch-up or immediate retries, is the intended
cadence. The sampler records the attempt before launching and bounds execution;
collection does not itself invoke or retry a probe. Preserve `rate_limit_event`
output even when the probe exits rejected. Publish each completed capture by
atomic replacement into a protected data directory, preserving its actual
observation mtime. Do not copy old events into a newly dated capture, touch old
capture files, or retain prompt/response text in the textfile or numeric state.
The exporter ignores non-rate-limit stream rows.

Native stream events have `type: rate_limit_event`, a `rate_limit_info` object,
`status` (`allowed`, `allowed_warning`, `rejected`) and optional camelCase fields
`rateLimitType`, `utilization`, `resetsAt`. Utilization is a **0–1 fraction**;
reset time is Unix **seconds**. The adapter also accepts the reference's
`rate_limit_info.unifiedWindows` recording shape. Native statusline
`used_percentage` (0–100) is a different contract and is not accepted here.

These are transition events, not complete account snapshots. A missing window
or utilization remains unknown. A later event without utilization preserves
the prior value and its original observation time. Replaying an older capture
cannot replace newer observations. Reset observation age is tracked separately.
The bars and reset panels hide fields older than 30 minutes; the observation-age
panel still exposes the age of retained stale values.

A rejected named window is always **1.0**, even when native utilization is
missing or zero. Numeric exhaustion is capped at 1.0. A rejection without a
supported window conservatively marks both windows 1.0 and exports
`claude_max_rejection_assumed=1`; it does not assert that both were measured full.
No reset time is invented. Malformed values and JSON increase a bounded error
count; missing sources do not become zeros.

## Collect recorded data

Use the script's PEP 723 dependency pin with upstream `uv run --script`, or
install the hash-pinned `prometheus-client` wheel from
`.github/requirements-ci.txt` into a dedicated interpreter. The CLI explicitly
names every account capture; repeat `--capture` for the pool:

```sh
uv run --script observability/claude_usage_metrics.py \
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
queries. Reset panels multiply seconds by 1000 for `dateTimeAsIso`. API queries
require a successful complete ledger collection, and usage/spend panels expire
when collection is older than 30 minutes. No query supplies an artificial zero.
Generate and check the committed dashboard through the normal builder:

```sh
python3 observability/ns2604_dashboards.py
python3 observability/ns2604_dashboards.py --check
python3 -m unittest tests.test_claude_usage_metrics tests.test_ns2604_dashboards -v
python3 scripts/validate.py
```

The unit-test interpreter must have CI dependencies installed. The native
query test additionally uses upstream `promtool` from PATH or the
`CLAUDE_USAGE_PROMTOOL` environment variable. Its synthetic series prove that
the real five-hour bar query returns exhausted-account 1.0, excludes a stale
account, converts reset seconds to milliseconds, and expires API data when
collection stops. This optional native-tool test does not launch a probe.
The source selection, version pins and reproduced boundaries are recorded in
[the decision record](decisions/2026-10-10-claude-usage-observability.md).
