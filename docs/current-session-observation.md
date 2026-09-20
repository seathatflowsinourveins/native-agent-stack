# What was live in this session?

Observed September 20, 2026, 14:16–14:19 UTC, in the running Desktop Codex task.
This is a dated runtime receipt, not a claim that every catalog repository runs
continuously or that another PC has passed these checks. The machine-readable
[observation manifest](../evidence/receipts/current-session-observation-20260920.json)
retains commands, returned fields, timing, correlation and limits.

## Direct answers

| Layer / upstream repository | Observed in this task | Boundary |
| --- | --- | --- |
| [Context Mode](https://github.com/mksglu/context-mode) | Loaded MCP executes code and returns statistics; native MCPorter bridge reads the actual project file | This older directly loaded connection still rejects project-file reads because it retains the plugin directory as its root |
| [Serena](https://github.com/oraios/serena) | Active agent-lab project, ready language server, exact pattern retrieval returns the requested source line | Active language server is Bash; pattern search is not proof of Python semantic analysis |
| [SocratiCode](https://github.com/giancarloerra/SocratiCode) | Healthy Qdrant/embedding service; 196 indexed chunks; watcher active; semantic search returns the selected source function | Existing project index only; the compatibility provider label says LM Studio while this host uses local vLLM |
| [ai-memory](https://github.com/akitaonrails/ai-memory) | Loaded MCP returns this exact active session and fresh tool-lifecycle observations | Some captured outer-exec events have unknown tool family/outcome; they are not a complete native transcript |
| [RTK](https://github.com/rtk-ai/rtk) | Explicit native command executed; returned meter increase independently matches its SQLite record | Explicit Codex use; no automatic RTK rewrite for this task was established |
| [MCPorter](https://github.com/openclaw/mcporter) / [jCodeMunch](https://github.com/jgravelle/jcodemunch-mcp) | Upstream command bridge responds; jCodeMunch returns its retained estimate of 29,820 | jCodeMunch is not directly exposed in this Desktop task's loaded MCP tool catalog; this probe reads statistics |
| [Headroom](https://github.com/headroomlabs-ai/headroom) | Native savings command responds: zero global calls and zero saved tokens in its last-30-day ledger | Available explicit artifact lane; no evidence that it automatically compresses this conversation |
| [OpenTelemetry Collector Contrib](https://github.com/open-telemetry/opentelemetry-collector-contrib), [Prometheus](https://github.com/prometheus/prometheus), [Loki](https://github.com/grafana/loki), [Grafana](https://github.com/grafana/grafana) | Running services; seven Prometheus targets up; exact-parent Loki tool and response events observed | Service health, event delivery and consumption reconciliation are separate checks |
| [otel-tui](https://github.com/ymtdzzz/otel-tui) | Installed optional viewer; no running process found | It is not the active collector. No running Alloy process was found either |

The native bridge read the project's AGENTS.md and returned 8,689 bytes with
SHA-256 `2bf8707272db1a9271cbbb2c69ac8402dd4423775a0b9658b178868e0186f066`.
The failed direct MCP read is retained alongside that success. The existing
supported project-root registration is for fresh client connections; this check
did not restart the task or widen file-access permissions.

## Upstream commands and returned results

These are the installed upstream interfaces used for the probes. Substitute the
chosen project/index/config paths on another PC. The receipt distinguishes exact
returned values from derived summaries and parameterized command recipes.

```bash
rtk gain --format json
rtk git log -3
rtk gain --format json

headroom savings --json

mcporter call --stdio jcodemunch-mcp \
  --env CODE_INDEX_PATH="$HOME/.code-index" \
  --env JCODEMUNCH_SHARE_SAVINGS=0 \
  --tool order --args '{"action":"get_session_stats","args":{}}' \
  --output json --no-oauth
```

RTK returned 54 commands / 1,708 estimated saved tokens before the probe and
55 / 1,722 afterward. Independent SQLite inspection found row 55 for
`rtk git log -3`: input 118, output 104, saved 14, duration 9 ms. That verifies
the native meter's update; it is not an exact provider-token reduction.

The native Context Mode bridge used its existing scoped configuration:

```bash
mcporter --config "$MCPORTER_CONFIG" call context-mode.ctx_execute_file \
  --args '{"path":"<PROJECT>/AGENTS.md","language":"python","code":"import hashlib; print(len(FILE_CONTENT.encode()), hashlib.sha256(FILE_CONTENT.encode()).hexdigest())"}' \
  --output json --no-oauth
```

Direct MCP probes used the upstream tools `ctx_execute`, `ctx_execute_file`,
`ctx_stats`, `codebase_health`, `codebase_status`, `codebase_search`,
`get_current_config`, `search_for_pattern`, `memory_status` and
`memory_read_session_observations`. The latter used the actual parent session
identity with explicit workspace/project scope; a subagent's session ID is
different and must not be substituted.

## Observation commands

Native agent logs and metrics enter the local OpenTelemetry Collector. Its
privacy processors feed logs to Loki and metrics to Prometheus; Grafana reads
those backends. Context Mode and ai-memory lifecycle stores form a separate
observation path. RTK maintains its own command accounting database. Matching
these scoped records supplies corroboration without adding their counters.

These ports and unit names belong to the recorded Linux/WSL profile. Use the
selected host's native recipe when adopting the stack elsewhere.

```bash
systemctl --user is-active ecosystem-otelcol.service \
  ecosystem-prometheus.service ecosystem-loki.service ecosystem-grafana.service \
  ecosystem-alertmanager.service ecosystem-ntfy.service

curl --fail-with-body --silent --show-error http://127.0.0.1:14333/
curl --fail-with-body --silent --show-error http://127.0.0.1:19090/-/ready
curl --fail-with-body --silent --show-error http://127.0.0.1:13100/ready
curl --fail-with-body --silent --show-error http://127.0.0.1:13000/api/health

curl --fail-with-body --silent --show-error --get \
  http://127.0.0.1:19090/api/v1/query --data-urlencode 'query=up'
```

All six units returned `active`; all seven scrape targets returned `1`.
Collector, Prometheus and Grafana health returned HTTP 200. Loki initially
returned HTTP 503 with its 15-second readiness delay, then HTTP 200 at 14:18:31
UTC. Both outcomes are retained.

Set `DESKTOP_THREAD_ID` to the actual parent task identity before this native
Loki query. Public evidence identifies that scope by SHA-256 and omits the raw ID.

```bash
curl --fail-with-body --silent --show-error --get \
  http://127.0.0.1:13100/loki/api/v1/query \
  --data-urlencode "query=sum by (service_name) (count_over_time({service_name=~\".+\"} | conversation_id = \"${DESKTOP_THREAD_ID}\" or thread_id = \"${DESKTOP_THREAD_ID}\" or session_id = \"${DESKTOP_THREAD_ID}\" or ecosystem_task_id = \"${DESKTOP_THREAD_ID}\" [24h]))"
```

At 14:18:02 UTC this returned 2,778 records for the parent task from
`codex-app-server`. A bounded metadata sample independently matched root tool
responses to that same parent's Loki events. Exact match details are in the
receipt; transport success alone is not proof that a returned search found code.

The directly loaded ai-memory endpoint returned an active session with no end
time, 3,578 observations overall and 3,556 observations matching the requested
pre/post-tool filter, including fresh events at 14:17:58 UTC. An independent
Context Mode metadata read also found this exact parent task's lifecycle events,
including three PreCompact events. That does not rewrite the earlier fresh-native
trial in which PreCompact was never triggered.

## What the counters do and do not establish

The current Context Mode connection returned the rounded upstream footer
`1.1M tokens saved`, `98.9% reduction`, and `$5.33 this session / $5.67 lifetime`.
Its own output spans multiple projects/conversations. These are upstream
byte/event estimates and illustrative prices, not an exact lifetime provider
saving or a meter confined to this turn.

Loki response-completed examples returned 99,957 and 102,400 consumed tokens.
Each equals its own input plus output; cached input and reasoning output are
subsets. They are response-scoped examples, not this task's lifetime total.

Current Prometheus/Loki consumption equality is **not established**: the
retained Prometheus token series lack the exact task scope needed to join these
Loki response events. The specific six-hour SDK-worker query returned no series,
while unscoped Codex app-server series exist. Earlier empty fixture queries did
not establish an absence of all live telemetry.

After meaningful efficiency work, run `ecosystem-token-report refresh` to retain
current native snapshots. Keep native estimates, unique artifact comparisons and
provider consumption separate. Verification calls themselves can increment
counters; they must not be presented as productive savings or multiplied by the
repository count.
