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
