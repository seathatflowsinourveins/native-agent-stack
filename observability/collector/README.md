# Native Collector profile

Pinned distribution: `otelcol-contrib` **0.161.0**, Linux amd64, from the official
[release](https://github.com/open-telemetry/opentelemetry-collector-releases/releases/tag/v0.161.0).
Archive SHA256: `778c689efa681ff6e4722ce9f66b9b7f57c3ba009ab2e2b43dc2e0315862c731`.
The downloaded publisher `.sha256` file matched before extraction.

These are upstream installation commands for a new explicit installation path.
Do not overwrite an existing installation or customized configuration.

```bash
version=0.161.0
asset="otelcol-contrib_${version}_linux_amd64.tar.gz"
release="https://github.com/open-telemetry/opentelemetry-collector-releases/releases/download/v${version}"
mkdir -p "$PRIVATE_DOWNLOAD_DIR" "$COLLECTOR_INSTALL_DIR"
curl --fail --location "$release/$asset" -o "$PRIVATE_DOWNLOAD_DIR/$asset"
curl --fail --location "$release/$asset.sha256" -o "$PRIVATE_DOWNLOAD_DIR/$asset.sha256"
expected="$(cat "$PRIVATE_DOWNLOAD_DIR/$asset.sha256")"
(cd "$PRIVATE_DOWNLOAD_DIR" && printf '%s  %s\n' "$expected" "$asset" | sha256sum --check -)
tar -xzf "$PRIVATE_DOWNLOAD_DIR/$asset" -C "$COLLECTOR_INSTALL_DIR"
"$COLLECTOR_INSTALL_DIR/otelcol-contrib" --version

# Create a private persistent root and copy the reviewed configuration.
mkdir -p "$STACK_DATA_ROOT/collector/queue" "$STACK_DATA_ROOT/sdk-receipts" "$STACK_CONFIG_ROOT"
chmod 700 "$STACK_DATA_ROOT" "$STACK_CONFIG_ROOT"
install -m 600 observability/collector/collector.yaml "$STACK_CONFIG_ROOT/collector.yaml"
export ECOSYSTEM_OBSERVABILITY_DATA="$STACK_DATA_ROOT"
"$COLLECTOR_INSTALL_DIR/otelcol-contrib" validate \
  --config="$STACK_CONFIG_ROOT/collector.yaml"
"$COLLECTOR_INSTALL_DIR/otelcol-contrib" \
  --config="$STACK_CONFIG_ROOT/collector.yaml"
```

For persistent hosting, install the [user-service example](ecosystem-otelcol.service.example)
with explicit absolute paths substituted for `@COLLECTOR_INSTALL_DIR@`,
`@CONFIG_ROOT@`, and `@DATA_ROOT@`, then use native `systemctl --user enable --now`.
The active acceptance service uses this layout and `UMask=0077`.

Ports: OTLP HTTP14318, OTLP gRPC14317, readiness14333, native metrics18889,
Collector self-metrics18888. Every listener is loopback. Logs go to native Loki
OTLP and a rotating local evidence file; 10MiB rotations with3backups bound the
file lane. The persistent retry queue is bounded to1000requests, and metric
conversion to10000streams with1hour stale expiration. Source grouping/restarts
still affect metric continuity; do not infer exactly-once delivery or billing.

All native log bodies are replaced, and resource/log/metric attribute maps use
allowlists. Resource/scope schemas, scope names/versions, log severity text and
top-level event names, metric descriptions/metadata and exemplars are normalized
or cleared. Selected private session/turn/process IDs remain for correlation.
Native event names, metric names, units and other allowlisted values assume
trusted instrumentation; this is not arbitrary-content DLP. The separate local
HTTP-health pipeline observes only its explicit non-secret loopback targets.

The profile exports logs and metrics only. `trace_exporter="none"` remains
explicit in the client example. Adding a tracing database is a separate
instrumentation and retention decision, not necessary for the accepted local
monitoring loop. Do not collect prompt/tool bodies to make a dashboard prettier.

## Run, tool and estimated-cost correlation — 2026-09-27

The logs pipeline retains `cost_usd` and `tool_use_id`, alongside the existing
`session.id`, `workflow.run_id` and `ecosystem.task.id`. This closes the
Collector configuration residual from #364 for Claude token-adoption
reconciliation. The existing `transform/privacy` allowlist uses the native
[Transform Processor](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.161.0/processor/transformprocessor/README.md)
and [`keep_keys`](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.161.0/pkg/ottl/ottlfuncs/func_keep_keys.go)
from `open-telemetry/opentelemetry-collector-contrib` **v0.161.0**.

The [Claude Code monitoring documentation](https://code.claude.com/docs/en/monitoring-usage),
checked live on 2026-09-27 with installed Claude Code 2.1.283 and its
[release notes](https://github.com/anthropics/claude-code/releases/tag/v2.1.283),
documents these fields:

| Native source | Retained attribute and meaning |
| --- | --- |
| `claude_code.api_request`, attribute `event.name="api_request"` | `cost_usd` is estimated USD cost; `input_tokens`, `output_tokens`, `cache_read_tokens` and `cache_creation_tokens` report request usage. |
| `claude_code.tool_result` / `claude_code.tool_decision`, attributes `event.name="tool_result"` / `"tool_decision"` | `tool_use_id` identifies the invocation and matches hooks. A rejected tool call has a decision event and no result event. |
| Workflow agents and their descendants, since Claude Code 2.1.202 | `workflow.run_id` is emitted on their API/tool events and starts with `wf_`. It is absent on other events. |
| Caller-supplied `OTEL_RESOURCE_ATTRIBUTES` | Custom keys go in the OTLP resource block and are also attached as "attributes on every metric datapoint and event record" ([Multi-team organization support](https://code.claude.com/docs/en/monitoring-usage#multi-team-organization-support)). `ecosystem.task.id` is this repository's launcher-supplied run key; both log copies map to `ecosystem_task_id` in Loki. `transform/privacy` drops the datapoint copy and the metric resource copy. |

The [E2E RUNBOOK](../../evidence/artifacts/token-adoption-e2e-20260926/RUNBOOK.md#loki-queries-and-reconciliation--aa-7-84-steps-67)
exports `ecosystem.task.id=<run>` and uses the distinct Workflow identifiers
to split arms. For a non-Workflow invocation, supply a resource value that
distinguishes the intended arm/task/attempt (the preregistration's
`<run>.<arm>.<task>.<attempt>` format), or retain an independent session-to-arm
mapping. A shared run value alone cannot identify the arm. The Collector
preserves supplied identities; it does not invent a Workflow ID or fill in a
missing cost with zero. The existing Workflow ID shape guard still applies.

The [Loki template](../backends/templates/ecosystem-loki.yml.example) indexes
only `service.name`. Loki's native
[OTLP mapping](https://grafana.com/docs/loki/latest/send-data/otel/#format-considerations)
keeps the remaining attributes as structured metadata and normalizes dots to
underscores. Use pipeline filters, for example:

```logql
{service_name="claude-code"} | ecosystem_task_id="<run>" | workflow_run_id="<arm-workflow>" | event_name="api_request"
{service_name="claude-code"} | ecosystem_task_id="<run>" | session_id="<session>" | tool_use_id="<tool-invocation>"
```

For whole-run views that include `<run>.<arm>.<task>.<attempt>` values, use
Loki's [regex label filter](https://grafana.com/docs/loki/latest/query/log_queries/#label-filter-expression)
`ecosystem_task_id=~"<run>(\\..+)?"`; escape any regex metacharacters in the
actual run token. Keep exact matches for single-arm values or the shared run
value plus a Workflow ID, as above. Equality on `<run>` alone excludes suffixed
values and undercounts the whole run.

These filters select metadata; the scrubbed body cannot supply it through
`| json`. Retained identities remain private. Metrics keep their existing
writer identity and gain no run, tool-invocation or cost labels. `cost_usd`
is an estimate, not a billed amount or a replacement for the experiment's
dated token-pricing method. Confirm delivery and flushes before reconciliation;
missing telemetry remains unknown.

Validation: `python3 -m unittest tests.test_observability_run_correlation -v`.
The always-on allowlist regression fails if either required field is dropped.
With PyYAML and the documented Collector **0.161.0** and Loki **3.7.8** binaries,
the native test sends synthetic OTLP records through the committed logs
processors and exporters to isolated loopback services. It checks workflow arm
token sums, matching resource/event copies of the run key, whole-run prefix and
single-arm queries, session/tool joins, string/numeric/zero costs, absent values,
Codex argument removal and retained measurement metadata, the Codex launch-tag and
call-id joins ([below](#codex-launch-tag-and-call-id--2026-09-29)), and indexed series through
Loki's [query and series APIs](https://grafana.com/docs/loki/latest/reference/loki-http-api/).
Those native checks skip when their optional dependencies are absent. A skip is
not a pass: run them with an interpreter that has PyYAML and confirm zero skips.
This is **local integration with synthetic fixtures**; it is not a new provider
run, an unchanged upstream test suite or proof of deployment on the active host.

**Dated clarification, 2026-09-27:** base `ec27a300` already kept the resource
run key and `workflow.run_id` (added in #366, `a464d288`, after #364 merged at
`c71d66d0`); `tool_use_id` and `cost_usd` were still missing. The historical
RUNBOOK's opening "four merge gates" paragraph, its "Check delivery and
exporter flushes" paragraph under [Loki queries and reconciliation](../../evidence/artifacts/token-adoption-e2e-20260926/RUNBOOK.md#loki-queries-and-reconciliation--aa-7-84-steps-67),
and the [E2E README's #364 dependency row](../../evidence/artifacts/token-adoption-e2e-20260926/README.md#merge-before-run-dependencies-and-unverified-boundaries)
describe earlier inspected revisions. Those receipts are sealed by the #381
preregistration: RUNBOOK.md by hash, and the E2E README through its append-only
amendment rule. So they stay unchanged here, and their correction belongs to a
dated #381 amendment. Until that lands, this section supersedes their
field-gap statements. Host delivery/flush proof and
Codex `env`/`call_id` reconciliation remain outstanding. The Collector part of the
latter is updated in [Codex launch tag and call id](#codex-launch-tag-and-call-id--2026-09-29).

On a host already running the profile, `apply.sh` [leaves log_statements unchanged](../../evidence/artifacts/telemetry-writer-identity-20260926/host/merge_collector.py#L116),
so a log-statement change needs its own host step. The
[installation recipe above](#native-collector-profile) is for a new installation.
Do not copy the repository `collector.yaml` over a host file that has its own
receivers or ports. Do not assume the host's transform statements equal the
repository's; diff them first, then:

1. Print the host file's `transform/tool_names` and `transform/privacy` log
   statements next to the repository's base revision, in order, from a YAML parser.
2. Reconcile any other difference first, or record it. Then patch only the
   statements the change touches, in place and in order.
3. Run `otelcol-contrib validate` on the patched host file.
4. Restart with `systemctl --user restart ecosystem-otelcol.service` outside
   any measured window, and record the restart time.
5. Read back that the host's statements now equal the repository's, in order.
6. Prove delivery and flushes afterward.

Records sent while the Collector restarts are unknown, not zero.

Codex **rust-v0.157.1** logs full `arguments` in
[`tool_result.rs:55-79`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/otel/src/tool_result.rs#L55);
`[otel.tool_result] max_bytes=0` limits only the output preview
([line 94](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/otel/src/tool_result.rs#L94)).
The privacy transform explicitly deletes `arguments` as well as excluding it
from `keep_keys`, after the existing tool-name extraction/content removal.
It keeps `tool_name`, `tool_namespace`, duration, success, correlation fields,
`output_truncated` and any supplied `arguments_length`, `output_length` and
`output_line_count`. Those three sizes belong to upstream's trace branch
([log/trace split](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/otel/src/events/shared.rs#L59));
this logs-only profile does not synthesize them or claim Codex logs emit them.
The existing guarded mapping of native `mcp_server` to `mcp_server.name` becomes
`mcp_server_name` in Loki. Use `tool_namespace="mcp__context_mode"` for Codex
context-mode invoke-rate queries, including calls with absent server metadata;
the [direct/code-mode source paths](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/src/tools/call_trace.rs#L38)
are distinct. No live host privacy acceptance is inferred from fixture results.

### Codex launch tag and call id — 2026-09-29

The logs pipeline now keeps two Codex identities that it used to drop:

- the resource attribute `env`, which is the per-launch tag;
- the record attribute `call_id`.

Both appear in Loki as structured metadata named `env` and `call_id`. Sources
are openai/codex **rust-v0.157.1** (`36650394`) and the OTTL functions of
opentelemetry-collector-contrib **v0.161.0**:

| Native source | Retained attribute and meaning |
| --- | --- |
| `codex exec -c otel.environment=<tag>` ([`provider.rs:53,381`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/otel/src/provider.rs#L371-L389); config key at [`types.rs:605-606`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/config/src/types.rs#L605-L606), default `dev`) | `env` is the launch tag, on every log record of that process: the resource value, which Loki [replicates onto each entry](https://grafana.com/docs/loki/v3.7.x/send-data/otel/). |
| `codex.tool_result` ([`tool_result.rs:61`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/otel/src/tool_result.rs#L54-L80)) and `codex.tool_decision` ([`session_telemetry.rs:1112,1121`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/otel/src/events/session_telemetry.rs#L1098-L1125)) | `call_id` identifies the call and pairs a decision with its result. Model calls use `call_…` ids. A nested code-mode call gets `exec-<uuid v4>` ([`delegate.rs:323`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/src/tools/code_mode/delegate.rs#L323)). |

Changes in `collector.yaml`:

- `transform/privacy`, resource context: a new
  [`delete_key`](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.161.0/pkg/ottl/ottlfuncs/README.md#delete_key)
  guard, then `env` added to the resource `keep_keys`.
- `transform/tool_names`, last group: a new `delete_key` guard for `call_id`.
- `transform/privacy`, log context: `call_id` added to `keep_keys`, right after
  `tool_use_id`.

That is four statements: two guards added and two allowlists extended. Apply them
on a host with the diff-then-patch procedure above.

Each guard deletes a value unless it matches `^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$`.
This is the registry-name character class, at most 128 characters. It uses
[`IsMatch`](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.161.0/pkg/ottl/ottlfuncs/README.md#ismatch),
which converts any value type to a string and returns false for nil, so the
guard cannot fail under `error_mode: propagate`.

- The 24-character letter/digit rule for registry names does not apply here,
  because call ids contain such runs by design.
- A deleted value is an unknown identity, never a zero or a fabricated tag.
  Launch tags must fit the pattern before launch.
- `host.name`, which Codex adds to its logs resource, stays dropped.
- The metric resource allowlist is unchanged. Codex also puts `env` on its
  metrics resource ([`metrics/client.rs:46,345`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/otel/src/metrics/client.rs#L345)),
  and neither key becomes a metric label.

The Loki template indexes only `service.name`, and the native test checks that
neither key becomes an index label. Queries use pipeline filters:

```logql
{service_name="codex_exec"} | env="<tag>" | event_name="codex.tool_result" | call_id="<call>"
{service_name="codex_exec"} | env="<tag>" | event_name="codex.tool_decision" | call_id="<call>"
```

`codex.agent_communication` events carry no `conversation.id`
([`agent_communication.rs:44-66`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/src/agent_communication.rs#L44-L66)).
Because the tag is a resource attribute, these events still carry `env`.

Validation: `tests.test_observability_run_correlation` and
`tests.test_observability_tool_names`.

- An always-on check, which needs no PyYAML, requires both guards, both
  allowlist entries and their absence from the metric statements. The `env`
  guard must come before the resource allowlist. The `call_id` guard must be
  in the last `transform/tool_names` group, which has no conditions.
- The native test sends `codex_exec` records through the committed processors
  on Collector 0.161.0 into Loki 3.7.8. Each valid id is returned exactly once
  under its tag, and the decision pairs with its result. A 129-character id,
  an id with spaces, a tag with spaces, `host.name` and all content are
  dropped; a 128-character id is kept.

This is local integration with synthetic fixtures.

Limits:

- **Host.** This repository change is not host application. Until the host
  file is patched, validated, restarted and read back, the host Collector
  still drops both keys.
- **No real launch yet.** A real Codex launch with a tag has not been observed
  through this profile. The end-to-end join of Codex rollout or JSON output
  against Loki is still open for the token-adoption E2E, and belongs to its
  next dated amendment.
- **Some calls log no event.** Some dispatched Codex calls end with neither a
  `codex.tool_result` nor a `codex.tool_decision`:
  - a call blocked by a PreToolUse hook
    ([`registry.rs:598-612`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/src/tools/registry.rs#L598-L612));
  - a call whose hook-rewritten input fails
    ([`registry.rs:619-634`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/src/tools/registry.rs#L619-L634));
  - a nested code-mode payload error
    ([`code_mode/mod.rs:363-379`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/src/tools/code_mode/mod.rs#L363-L379));
  - a nested call cancelled before dispatch
    ([`delegate.rs:335-337`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/src/tools/code_mode/delegate.rs#L335-L337)).

  All four return before the registry logs a result
  ([`registry.rs:667-682`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/src/tools/registry.rs#L667-L682)).
  So Loki's `codex.tool_result` count can be lower than the rollout's function
  calls, and those calls are unknown in Loki rather than matched. A command the
  exec policy forbids is also rejected without a `codex.tool_decision`
  ([`orchestrator.rs:196-198`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/src/tools/orchestrator.rs#L196-L198)).
- **Other services.** Any other service that sets a resource `env` that fits
  the pattern now keeps it too.
- **Local display.** Retained identities stay private, as the session and
  tool-invocation ids already do. The local Grafana logs panels show every
  retained field in their log details, now including `env` and `call_id`:
  the backend template's sanitized-events panel and the grand-dashboard and
  native-data activity panels. They are served to loopback anonymous Viewer
  access only. Publish counts only; never a tag value or an id.

## Writer identity and counter integrity

Changed after `v2026.09.26.2`. A Prometheus series is identified by `job`
(`service.name`), `instance` (`service.instance.id`) and the allowlisted data
point labels. Before this change every Claude process and every directly
launched Codex process was `instance="unscoped"`, so writers shared series:

- Claude's cumulative counters from concurrent processes overwrote each other.
  A raw sum showed whichever process wrote last; `increase()` read each
  alternation as a reset. On the workstation on 2026-09-26 (14:51-15:51Z, with
  concurrent sessions), `increase()` was 73 to 193 times the Loki `api_request`
  sums per token type, with 7,216 counter resets.
- Codex sends delta points. `delta_to_cumulative` rejects a point that is not
  newer than its stream (`delta.ErrOutOfOrder`) or starts before it
  (`delta.ErrOlderStart`). That hour it rejected about 3,518 of 8,160 points
  (`increase()` estimates of its self-metric). A
  window comparison with Loki cannot size the Codex loss, because Codex records
  a turn's tokens when the turn ends; the proof compares completed processes.
- The allowlist also merged streams inside one process: Claude token and cost
  counters carry `agent.name`, `skill.name`, `mcp_server.name` and more,
  Codex metrics carry `phase`, `feature` and others. `keep_keys` alone left
  same-identity duplicates in one export.

The profile now gives every writer its own series with upstream mechanisms:

1. Claude sets `OTEL_METRICS_INCLUDE_SESSION_ID=true`, Claude Code's
   documented default ([monitoring](https://code.claude.com/docs/en/monitoring-usage)),
   in [its settings example](claude-settings.json.example) and
   `adoption/templates/claude.settings.template.json`. `groupbyattrs/session`
   moves `session.id` onto a resource of its own, and `transform/privacy`
   makes it `service.instance.id` before the resource allowlist drops it. A
   launcher-set `service.instance.id` is kept, with `/<session.id>` appended.
   `/clear` assigns a new `session.id` in the same process, so each session is
   a writer. A resumed session keeps its `session.id` in a new process, so each
   of its type and cost series resets once; `increase()` handles that, and the
   reset alert counts resets per series, so it stays silent. Cumulative
   temporality stays: Prometheus expects it, and a Collector restart then loses
   nothing.
2. Codex (rust-v0.157.1) exports no per-process attribute on its metrics, but
   its `opentelemetry_sdk` 0.31 `Resource::builder()` reads
   `OTEL_RESOURCE_ATTRIBUTES` for metrics and logs. The
   [identity launcher](codex-identity-launcher.sh.example), a local
   integration, adds a fresh `service.instance.id`, then runs the real codex.
   An inherited id (from a shell, worker or parent codex that set one) becomes
   the prefix, `<inherited>/<fresh>`, so concurrent children of one parent stay
   separate writers, as the repository's workers do for their subprocesses.
   Scratch variables use the `__codex_identity_` prefix inside a subshell, so
   inherited exported variables keep their values in the child; only
   `OTEL_RESOURCE_ATTRIBUTES` changes. Quoted `"$@"` preserves empty arguments,
   whitespace, quotes and newlines. Attribute parsing follows
   [opentelemetry-rust v0.31.0](https://github.com/open-telemetry/opentelemetry-rust/blob/v0.31.0/opentelemetry-sdk/src/resource/env.rs):
   comma-separated entries, the first `=`, trimmed keys and values, and the
   last duplicate identity. The launcher remains POSIX sh compatible.
   The Loki records of that process carry the same value as
   `service_instance_id`.
3. In `transform/privacy`, `aggregate_on_attributes("sum", <allowlist>)` adds
   together the sum and histogram streams that the allowlist collapses
   (delta points only when they share start and end times). Gauges and
   summaries keep plain `keep_keys`.
4. The Collector's Prometheus exporter sends each stream's start time.
   Prometheus runs with `created-timestamp-zero-ingestion`, so a new
   per-process series starts from an injected zero and its first sample
   counts toward `increase()`, and with `promql-extended-range-selectors` for
   exact `increase(x[w] anchored)` windows (see the
   [backends README](../backends/README.md)).
5. Dashboards use `rate()` and `increase()` summed over writers and exclude
   `instance="unscoped"`. The `native-telemetry-integrity` alert group watches
   counter resets, dropped delta points and unscoped writers.
6. Per-process series multiply the Codex histogram buckets, which no dashboard
   or rule reads. The `collector-native` scrape drops them with
   `metric_relabel_configs`, keeping every `_sum` and `_count` and the
   `turn_token_usage` buckets, so the size-based retention
   (`--storage.tsdb.retention.size=512MB`) does not shorten the history of the
   other jobs in this Prometheus.

Install the launcher in place of the codex link on `PATH`, and run it again
after every Codex version switch, because the switch re-links `bin/codex`:

```bash
# Only over the bootstrap's absolute link (e.g. to $ECO_ROOT/tools/codex-0.157.1/bin/codex):
# if bin/codex is already a launcher, or its target is not executable, nothing changes.
link="$ECO_ROOT/bin/codex"
test -L "$link" && real="$(readlink "$link")" && [ -x "$real" ] \
  && sed "s#@CODEX_BIN@#$real#" observability/collector/codex-identity-launcher.sh.example > "$link.tmp" \
  && chmod 0755 "$link.tmp" && mv -f "$link.tmp" "$link" && "$link" --version
```

On a host that already runs the previous profile, the
[host recipe](../../evidence/artifacts/telemetry-writer-identity-20260926/host/)
does every step: `apply.sh` renders the configs with the repository renderers
and this host's port overrides, validates them (`otelcol-contrib validate`,
`promtool`, `systemd-analyze verify`, the launcher's `--version` against the
real codex) and shows each diff. Any failed check stops it before the first
change. The Collector merge checks the resulting config before writing its
candidate: every original statement, statement-group condition, processor
setting, pipeline and processor order must survive. The only permitted
processing changes are the repository's writer-identity additions and the
`deltatocumulative` alias rename. An extra host metrics processor, an extra
`transform/privacy` metric statement, or incompatible order produces a
non-zero refusal naming the affected config section;
`apply.sh` stops before installing anything. These checks respect the
[pinned transform processor's ordered execution](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.161.0/processor/transformprocessor/README.md).

The Prometheus merge keeps the host's existing `collector-native`
`metric_relabel_configs` first, in their original order, and appends only
missing repository bucket rules. Owned rules already present stay in place;
a second merge makes no change. Its guard checks that the original rules
survive exactly, only missing owned rules are appended, and all other host
settings are unchanged. This preserves
[Prometheus 3.15.0's rule execution order](https://github.com/prometheus/prometheus/blob/v3.15.0/model/relabel/relabel.go).

When `claude-setting` is selected, preflight requires
`~/.claude/settings.json` to be a regular file, not a symlink, and reads it
through `claude_setting.py` before rendering or installing any candidate.
Missing, unreadable, malformed, or non-object JSON settings cause a clear
refusal before any installation, backup, or service restart. A run that does
not select `claude-setting` does not require this file.

Before rendering, `apply.sh` records each selected file target's SHA-256,
including absent targets and the launcher's symlink destination. It checks
all those targets after validation and before the first install, then checks
each target again in `install_file()`. A change causes a non-zero refusal
naming the file; rerun to render and validate against the current files.
This follows the existing rollback digest guard. It detects stale candidates;
the hash check and filesystem rename are separate operations, so concurrent
writers still require coordination. The Claude settings step retains its
existing single-key update and rollback behavior.

`apply.sh --apply` copies every file it replaces to
`${XDG_STATE_HOME:-~/.local/state}/native-agent-stack/g1-writer-identity/backup-<UTC>/`
(mode 0700, outside `/tmp`), installs, restarts Prometheus and the Collector,
reads both back and prints the rollback command when a read-back fails. It
reads the running services back on every `--apply`, also a rerun whose files
are already in place, and restarts one that started before its files or lacks
part of the change. Prometheus is read at the port of its rendered unit.
`rollback.sh` restores the newest backup, all or nothing. `prove.sh` is the
read-only host acceptance check whose conditions the decision record below
lists; run it at least 3.5 minutes after the scenario's processes finish.

Privacy and cost: `session.id`, a random UUID, becomes the `instance` label
and the Loki `session_id` field. It was already on the log allowlist, and
account identifiers stay dropped. Each Claude session and Codex process now
has its own series. The exporter drops a series five minutes after its writer
stops (`metric_expiration`), and `delta_to_cumulative` keeps at most 10,000
streams for an hour. Under the one shared identity before the change, 1,388
of the 1,512 `codex_exec` series were histogram buckets (read-only count,
kept in the [before-change receipt](../../evidence/artifacts/telemetry-writer-identity-20260926/host-before-20260926.json));
the bucket drop above keeps per-process growth to the `_sum`, `_count` and
counter series. `prove.sh` reports head series, storage against the size
limit, size-based deletions and tracked delta streams.

A synthetic run (local integration, not host evidence) sent identical OTLP
input from three Claude-like and three Codex-like concurrent writers through
the old and new profiles on the pinned binaries. Old profile: 4 Claude
resets, totals 51 percent low, 24 of 70 delta points dropped, Codex totals
6.7 percent low. New profile: 0 resets, 0 dropped points, and exact totals
from `increase(... anchored)`. Plain `increase()` was 3.0 percent high: it
extrapolates at the window edge after a writer stops. The
[decision record](../../docs/decisions/2026-09-26-telemetry-writer-identity.md)
keeps the sources, both measurements, the alternatives and what would overturn
this choice.

Limits: a session started before the settings change stays `unscoped` until
it exits. A codex started from the real binary instead of `bin/codex` gets no
id of its own (`unscoped`, or the id it inherited, shared with its parent) and
no lane from `ECOSYSTEM_LANE`. A Codex version switch re-links `bin/codex` and
removes the launcher until it is installed again.

## Codex lane label

Changed in #671. Prometheus labels each Codex series with its lane name,
`ecosystem_lane`, which the backend dashboard's Codex lanes row and the
`ecosystem-lanes` alert rules group by. The label comes from the resource
attribute `ecosystem.lane`: `transform/privacy` keeps it only when it matches
`^[a-z][a-z0-9_-]{0,31}$`, and the Prometheus exporter's
`resource_constant_labels` makes it the only resource label. A writer without
a lane shows as `unattributed`.

The [identity launcher](codex-identity-launcher.sh.example) sets the attribute
from `ECOSYSTEM_LANE`, so a lane's launch only names its lane:

```bash
ECOSYSTEM_LANE=root codex
ECOSYSTEM_LANE=trading codex exec '<task>'
```

- A terminal profile puts the assignment in its command line, for example
  `bash -lc 'ECOSYSTEM_LANE=runtime exec codex'`. A lane relaunch script
  exports `ECOSYSTEM_LANE=<lane>` before it starts `codex`. Both must start
  the `codex` on `PATH`, the installed launcher, not the real binary.
- The value must match the Collector's pattern. The launcher drops any other
  value: it prints one warning on stderr, without the value, and still starts
  codex, with no lane. An empty value names no lane.
- An `ecosystem.lane` entry already in `OTEL_RESOURCE_ATTRIBUTES` wins, and
  `ECOSYSTEM_LANE` is not read. An entry counts when its key trims to
  `ecosystem.lane` and it has an `=`, which is what the SDK reads as the
  attribute ([`env.rs` L45-58 at v0.31.0](https://github.com/open-telemetry/opentelemetry-rust/blob/v0.31.0/opentelemetry-sdk/src/resource/env.rs#L45-L58)).
  A codex started through the launcher inside a lane process therefore keeps
  that lane. To name another lane there, replace the entry.

Validation: `tests.test_observability_writer_identity.LauncherTests` under
bash, sh and dash. `ECOSYSTEM_LANE=root` yields the attribute after any
inherited entries. Malformed values are dropped with the warning, including a
comma that would otherwise add a second `service.instance.id`. An explicit
entry wins. As a negative control, the launcher before this change (`1f5a791b`
on main) sets no lane for the same variable. This is local integration with a
stand-in codex, not a host launch.

Residuals:

- **Per-lane values.** This repository ships the variable and the recipe, not
  the lane assignments. The per-lane values come with the command center's
  relaunch scripts, its lane registry and terminal profiles. Until those set
  `ECOSYSTEM_LANE`, every lane exports no lane and shows as `unattributed`.
- **Host launcher.** The host's installed `bin/codex` is a render of the
  previous template. The installation block above replaces only the
  bootstrap's link. Over an installed launcher, the
  [host recipe](../../evidence/artifacts/telemetry-writer-identity-20260926/host/)'s
  `apply.sh --only codex-launcher` shows the change, and `--apply` installs
  it with a backup. Until then the host ignores `ECOSYSTEM_LANE`, and
  `prove.py` reports `equals_repository_template` as false.

## Tool, MCP, skill and subagent invoke rates

Proposed after the writer-identity change (see the
[decision record](../../docs/decisions/2026-09-26-tool-invoke-rates.md)). Both logs pipelines run
`transform/tool_names` just before `transform/privacy`. Metrics are unchanged: no name joins the
metric allowlist, so the writer identity above is untouched.

- **Claude Code names need `OTEL_LOG_TOOL_DETAILS=1`.** For user-configured MCP servers the event's
  `tool_name` is always `mcp_tool`. The server and tool names and the Agent tool's `subagent_type`
  appear only in `tool_parameters`, a JSON string that also holds whole Bash commands
  ([monitoring](https://code.claude.com/docs/en/monitoring-usage)). Both client examples set the flag.
  The processor parses `tool_parameters` into its statement cache and copies only `mcp_server_name`,
  `mcp_tool_name` and `subagent_type`, as `mcp_server.name`, `mcp_tool.name` and `subagent_type`.
  From `bash_command`, the command's first word, it keeps one boolean, `shell_rtk`. It never reads
  `full_command`. Skill names come from `skill_activated`, which Claude Code logs only for a skill it
  loaded; the Skill tool's `skill_name` is what the model typed and is not copied.
- **Codex needs no setting.** codex-cli 0.157.1 logs `mcp_server`, `agent_name` (`/root` or
  `/root/<task>`) and `originator` on `codex.tool_result`, and `kind`, `state` and both thread ids on
  `codex.agent_communication`. The server name is copied and the communication fields are kept.
  `agent_name` only decides `actor`: the task name in the path is chosen by the model, so the path is
  not exported. `shell_rtk` comes from `exec_command`'s `cmd`.
- **`client` groups by normalized originator name, not by process.** Every Codex app-server front-end
  exports `service.name` `codex-app-server`, so for that service `client` is the thread's `originator`;
  otherwise it is `service.name`. First-party `Codex <App>` originators become `codex_<app>`. Two separate
  app-server processes whose originator normalizes to the same name share one `client` label, and one
  app-server process also gives new threads the originator of the first client that initialized it, so two
  front-ends on one process share a `client` too.
- **Content is deleted twice.** This processor deletes `tool_parameters`, `tool_input`, `arguments`,
  `output`, `content` and `error`, and none of them is on the allowlist. `error_mode: silent` keeps a
  failed parse from writing its input to the Collector log; such a record carries
  `tool_details="unparsed"`.
- **Registry names are checked.** MCP server and tool names, skill names, `originator` and `client`
  are written by Claude Code or Codex from their own configuration. Each must match
  `^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$` and must not contain a run of 24 or more letters and digits.
  Anything else is exported as `other`: text with spaces, paths, addresses and key- or token-shaped
  strings.
- **Agent types are a closed list.** `subagent_type`, `agent.name` and `agent_type` keep only the
  built-in agents of the [subagent docs](https://code.claude.com/docs/en/sub-agents) (`general-purpose`,
  `Explore`, `Plan`, `claude`, `statusline-setup`, `claude-code-guide`), the workflow child
  (`workflow-subagent`) and `custom`. Any other value becomes `custom`, as Claude Code reports
  user-defined agents without the flag. Add a name to the list in `transform/tool_names` to count it.
- **Values the model types are not exported.** The Skill tool's `skill_name`, `workflow.name` (a
  workflow script's own name) and Codex agent paths never leave the Collector, whatever their shape.
- **Enumerations and ids are checked.** Derived values, `invocation_trigger`, `kind`, `state` and the
  ids must match their enumeration or pattern, or they are deleted.
- **Derived keys come only from this processor.** It first deletes any incoming `tool_family`, `actor`,
  `shell_rtk`, `tool_details` or `client`. SDK receipts share the allowlist, so for them the processor
  deletes every invoke-rate key and the Codex `call_id`.
- **Derived values are bounded.** `tool_family` is one of shell, read, edit, mcp, skill, toolsearch, web,
  agent, code_mode or other. `actor` is `main` or `subagent` for Codex (from `agent_name`). For Claude
  tool events it is `workflow` when the event has `workflow.run_id`, else `main_or_subagent`; Claude API
  requests get `main`, `subagent`, `workflow` or `auxiliary` from `query_source`.
- **Loki stores them as structured metadata** (its OTLP default; the template indexes only
  `service.name`), with dots as underscores: `mcp_server_name`, `skill_name`, `workflow_run_id`.
  Session, conversation, workflow run and thread ids stay structured metadata, and no panel groups by
  them.

Limits: Claude Code marks workflow children on their tool events but not Agent-tool subagents
(`agent_id` is a trace-span attribute, and traces stay off), so their calls count as
`main_or_subagent`. The dashboard adds each subagent's `total_tool_uses` from `subagent_completed`
and the per-actor MCP attribution of `api_request`; the latter counts requests, so several MCP
results consumed by one request count once. Codex `functions/exec` and `functions/wait` are the
code-mode wrapper (`code_mode`), and the calls inside it are counted as well. Claude sessions started
before the flag change carry no names. Custom agents count as `custom` until their names are added.

## SDK result receipts

`file_log/sdk_receipts` uses the upstream file receiver and JSON parser to ingest
completed private metadata files from `$STACK_DATA_ROOT/sdk-receipts`. It persists
read offsets and retries downstream refusals with backoff, pausing that receiver
until acceptance. Malformed JSON is dropped quietly by the native parser so an
invalid file cannot poison retries or print raw content in diagnostics; its
private source file remains available. Malformed/spool-overflow recovery was not
exercised. The SDK helper publishes a complete 0600 file atomically;
`ECOSYSTEM_SDK_OBSERVATION_DIR` or `--observation-dir` selects this existing private
directory. Its first field is a unique observation ID, so even identical outcomes
have different file fingerprints. Unknown additive usage remains absent, never zero.

This file lane is the Codex helper's receipt spool. Repository producer tracing
finds `blueprints/us-equities/workers/native_worker.py::write_observation` as its
native publisher; `research-runtime/run_worker.py` delegates its Codex role to
that helper, and the other spool writers are synthetic privacy/outage fixtures.
The template routes only `file_log/sdk_receipts` through `transform/sdk_receipt`.
Native Claude and other OTLP log producers use `logs`; native metric counters use
`metrics`. Those pipelines do not apply the receipt usage exclusion. No
supported additive non-Codex file-receipt schema is defined for this spool.

Codex SDK 0.159.2 returns a native `ThreadTokenUsage`: `total` accumulates across
the thread and `last` describes only the latest request, which can be one of
several requests in a turn. The SDK returns that object unchanged. See
[`_run.py`](https://github.com/openai/codex/blob/rust-v0.159.2/sdk/python/src/openai_codex/_run.py),
[`ThreadTokenUsage`](https://github.com/openai/codex/blob/rust-v0.159.2/sdk/python/src/openai_codex/generated/v2_all.py)
and [`TokenUsageInfo::append_last_usage`](https://github.com/openai/codex/blob/rust-v0.159.2/codex-rs/protocol/src/protocol.rs).
The private run result retains the native counters. Published observations keep
`usage_scope=native_thread_cumulative` and the native `usage_status`, but set
`usage` to null: this receipt path has no serialized preceding baseline that
would justify an additive delta. `last` is not substituted for turn usage.
The Collector preserves the scope and removes all SDK numeric token attributes,
including legacy receipt totals and prefilled fields, with its native
[`delete_matching_keys` transform](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.161.0/pkg/ottl/ottlfuncs/README.md#delete_matching_keys).
Consequently these observations do not contribute a value to the SDK token panel.

Per-record `receipt_id` survives as structured metadata. It must not be stored
on the shared resource: multiple records can share one resource group. The
Grafana panel excludes historical records lacking `receipt_id` and takes the
maximum reported total per receipt before summing within the selected dashboard
time range. This avoids counting a replay of the same receipt twice; it is not a
permanent financial ledger or a way to merge cumulative snapshots. The scope
exclusion happens before that query; a new receipt ID cannot make cumulative
usage additive. Reuse the original ID when replaying an observation. Already
stored historical records are not rewritten by this repository template.

The local integration check `tests.test_sdk_usage_scope` publishes constructed
observations through the real file receiver, repository processors, isolated
Loki, and the exact dashboard query. It covers cumulative start/resume snapshots,
replay under the same ID, republication under a new ID, missing/unknown scope,
and unavailable usage. Run with the documented native binaries and optional
PyYAML: `uv run --no-project --with PyYAML==6.0.3 python -m unittest tests.test_sdk_usage_scope -v`.
It performs no model inference; the snapshot values come from the prior native
qualification receipt. The [correction receipt](../../evidence/artifacts/runtime-sdk-20260930/usage-scope-receipt.json)
preserves the failing aggregate of 78,331 and the corrected native results.

Acceptance imported bounded summaries of two already-completed native SDK runs
through the same helper; it made no new inference after adding this publication
helper. Earlier private raw migration inputs remain private. Published summaries
omit final responses, items and raw errors; the Collector further filters them.
The initial SDK histogram was not observed. The [later native configuration
fix and fresh task](../session-e2e.md) now establish both histogram and automatic
receipt delivery. The two sources stay separate to prevent double counting.
The spool and receiver checkpoints are private retained files; no automatic
spool expiry or disk-pressure recovery acceptance is claimed.

## WSL host resources

The pinned upstream `host_metrics` receiver now collects CPU time/count, load,
memory and only the `/` filesystem every 30 seconds. Native validation and the
Prometheus query observed 8 families / 23 series. This pipeline uses trusted local
instrumentation, has no process-command-line scraper, and does not enumerate
other mountpoints. WSL virtual filesystem capacity is distinct from physical
Windows backing storage. Two new rules detect root free space below 5 GiB for 10 min
and absent root filesystem observations for 2 min; no disk exhaustion was induced.
The original full local notification route proof remains separately dated.

SDK/App Server metrics need the `[analytics]` opt-in in the complete Codex
user-config example. Review existing opt-outs and native first-party event
semantics before merging; see [the exact cause and repair](../session-e2e.md).
