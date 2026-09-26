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
change. `apply.sh --apply` then copies every file it replaces to
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
id of its own: `unscoped`, or the id it inherited, shared with its parent. A
Codex version switch re-links `bin/codex` and removes the launcher until it is
installed again.

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
- **`client` tells front-ends apart.** Every Codex app-server front-end exports `service.name`
  `codex-app-server`, so for that service `client` is the thread's `originator`; otherwise it is
  `service.name`. First-party `Codex <App>` originators become `codex_<app>`. One app-server process
  gives new threads the originator of the first client that initialized it, so two front-ends on
  one process still share a `client`.
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
  deletes every invoke-rate key.
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
exercised. The SDK helper publishes a complete0600 file atomically;
`ECOSYSTEM_SDK_OBSERVATION_DIR` or `--observation-dir` selects this existing private
directory. Its first field is a unique observation ID, so even identical outcomes
have different file fingerprints. Unknown usage remains absent, never zero.

Per-record `receipt_id` survives as structured metadata. It must not be stored
on the shared resource: multiple records can share one resource group. The
Grafana panel excludes historical records lacking `receipt_id` and takes the
maximum reported total per receipt before summing within the selected dashboard
time range. This avoids counting a replay of the same receipt twice; it is not a
permanent financial ledger or a way to merge independent receipts for one turn.
Reuse the original ID when replaying an observation; assigning a new ID to the
same turn creates a new accounting record.

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
