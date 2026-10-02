# Isolated upstream operations

Run from this package directory. These are supported upstream commands, not a
second evaluation runner. Inspect owns evaluation and logs. The checked-in
configuration disables model work for the restore probe; it is **not** a tuned
quality arm. Image pins and provenance are in [artifacts.json](artifacts.json).

## Runtime boundary

Use the dedicated profile and explicit context on every Docker command. No host
directory, credential store, Docker socket or host PID namespace is mounted into
a container. Named volumes stay private to this VM. Its default context must not
replace another session's context.

```sh
colima start --profile memory-qualification --cpus 4 --memory 12 --disk 32 \
  --mount none --vm-type vz --activate=false --ssh-config=false \
  --ssh-agent=false --template=false
docker --context colima-memory-qualification pull \
  docker.io/akitaonrails/ai-memory@sha256:8fd85dd8cb14e75ea62d74423565121b1cc2ed20d0016ed38b546e9082f16e65
docker --context colima-memory-qualification pull \
  ghcr.io/vectorize-io/hindsight@sha256:07873ca79a79bcb5662c6015bf9e40cf32fc0ae5bd7f5e8e71974fffa48e31c1
```

Existing containers are resumed with `docker start`, not recreated over an owned
name. Before starting a new run, inspect its named volumes and containers and
record whether it is a fresh fixture or a continuation. Docker Compose/buildx
were unavailable on the qualification host; native Docker commands suffice.

## Actual ai-memory restore procedure

This probe uses network `none`; CLI requests run inside the server's container
against its own loopback address. No host port or production memory is involved.
The restore target is a different volume and container. The source can remain
online: there is exactly one writer per volume and the restore process has its
own PID namespace. Do not bypass the upstream restore process guard.

```sh
docker --context colima-memory-qualification volume create qualification-ai-control
docker --context colima-memory-qualification create --name qualification-ai-control \
  --network none --cap-drop ALL --security-opt no-new-privileges \
  --mount type=volume,src=qualification-ai-control,dst=/data \
  docker.io/akitaonrails/ai-memory@sha256:8fd85dd8cb14e75ea62d74423565121b1cc2ed20d0016ed38b546e9082f16e65 \
  --config /etc/qualification.toml serve --transport http --bind 127.0.0.1:49374 \
  --workspace qualification --project control --no-watcher
docker --context colima-memory-qualification cp runtime/ai-memory.toml \
  qualification-ai-control:/etc/qualification.toml
docker --context colima-memory-qualification start qualification-ai-control
docker --context colima-memory-qualification exec qualification-ai-control \
  ai-memory --config /etc/qualification.toml status --json
docker --context colima-memory-qualification exec qualification-ai-control \
  ai-memory --config /etc/qualification.toml write-page \
  --workspace qualification --project control --path decisions/restore-probe.md \
  --title 'Isolated restore probe' \
  --body 'Synthetic qualification fixture. Current route is cedar; retired route is birch. Source: restore-probe-v1.'
docker --context colima-memory-qualification exec qualification-ai-control \
  ai-memory --config /etc/qualification.toml write-page \
  --workspace qualification --project producer --path notes/sender.md \
  --body 'Synthetic sender scope for restore probe.'
docker --context colima-memory-qualification exec qualification-ai-control \
  ai-memory --config /etc/qualification.toml message send \
  --from-workspace qualification --from-project producer \
  --to-workspace qualification --to-project control --subject restore-probe \
  'Synthetic pending work item restore-probe-v1; owner control; ACK required separately.' --json
docker --context colima-memory-qualification exec qualification-ai-control \
  ai-memory --config /etc/qualification.toml backup --to /data/control.tar.gz
docker --context colima-memory-qualification volume create qualification-ai-restored
docker --context colima-memory-qualification run --rm --name qualification-ai-restore \
  --network none --cap-drop ALL --security-opt no-new-privileges \
  --mount type=volume,src=qualification-ai-restored,dst=/data \
  --mount type=volume,src=qualification-ai-control,dst=/input,readonly \
  docker.io/akitaonrails/ai-memory@sha256:8fd85dd8cb14e75ea62d74423565121b1cc2ed20d0016ed38b546e9082f16e65 \
  restore --from /input/control.tar.gz --force
docker --context colima-memory-qualification create --name qualification-ai-restored \
  --network none --cap-drop ALL --security-opt no-new-privileges \
  --mount type=volume,src=qualification-ai-restored,dst=/data \
  docker.io/akitaonrails/ai-memory@sha256:8fd85dd8cb14e75ea62d74423565121b1cc2ed20d0016ed38b546e9082f16e65 \
  --config /etc/qualification.toml serve --transport http --bind 127.0.0.1:49374 \
  --workspace qualification --project control --no-watcher
docker --context colima-memory-qualification cp runtime/ai-memory.toml \
  qualification-ai-restored:/etc/qualification.toml
docker --context colima-memory-qualification start qualification-ai-restored
docker --context colima-memory-qualification exec qualification-ai-restored \
  ai-memory --config /etc/qualification.toml read-page --workspace qualification \
  --project control --path decisions/restore-probe.md --json
docker --context colima-memory-qualification exec qualification-ai-restored \
  ai-memory --config /etc/qualification.toml message list --workspace qualification \
  --project control --json
docker --context colima-memory-qualification restart qualification-ai-restored
```

Repeat the two reads after restart. Compare the exact body and message ID/state
with the originals. A wrong-project `read-page` must fail, and a missing archive
must not restore. Inspect the archive independently for `db/memory.sqlite` and
the page. `/etc/qualification.toml` is external to the data directory and was
absent from the archive; preserve and verify its hash separately. A backup to a
new root-owned `/snapshots` volume failed on this image's unprivileged user;
the corrected procedure uses the image-owned `/data` path. Do not broaden
container privileges to repair that permission failure.

Stop only the owned resources; retain volumes and logs for recovery:

```sh
docker --context colima-memory-qualification stop qualification-ai-control qualification-ai-restored
colima stop --profile memory-qualification
```

## Native Hindsight canary gate

The inert config installs nothing and has no opted-in paths. A single native
configuration owner first backs up the exact files the pinned installer will
touch and attests every effective user, managed, project and plugin hook, MCP
endpoint and startup-context source. Use the existing native sign-ins; never
change `HOME` or `CODEX_HOME` to simulate isolation. Bind a future candidate API
to loopback only, with a unique bank and exact opted-in checkout. Tune and freeze
its provider/embedding/reranker settings separately; this package does not
declare a disabled or reduced Hindsight pipeline its best quality configuration.

After the gate, set a private copy's `disabled` to false and its `optInPaths` to
the exact approved checkout. `CANARY_CONFIG`, `CANDIDATE_URL`, `CANARY_DIR`,
`PRIVATE_AI_DATA`, `PRIVATE_AI_URL`, and `AI_MEMORY_BIN` below are explicit
run-local paths/endpoints chosen and recorded by that owner, not global defaults.

```sh
HINDSIGHT_CONFIG="$CANARY_CONFIG" \
  npx @vectorize-io/hindsight-coding-agents@0.8.0 \
  install codex claude-code --server self-hosted --api-url "$CANDIDATE_URL"
AI_MEMORY_CAPTURE_OWNER=hindsight.codingagents \
  "$AI_MEMORY_BIN" --data-dir "$PRIVATE_AI_DATA" \
  hook --check-capture --event session-start --agent codex --server-url "$PRIVATE_AI_URL"
```

Capture suppression must report `external_capture=true` and
`admits_capture=false`. It **preserves** ai-memory startup context and handoffs;
therefore it cannot by itself qualify control/candidate isolation. A repository
server marker also does not redirect every MCP or managed launcher. Stop before
native capture if any effective source or endpoint remains unresolved.

For an accepted canary, run the 20 genuine sessions across both native clients
and two restarts required by the preregistration. No fixture replay counts as a
real session. Task completion and ACK records are durable state independent of
message pop/claim. On contamination, lost work, duplicate side effects or failed
recovery, stop the canary, retain its logs, use the pinned upstream uninstall,
then restore and verify the exact backed-up native configuration:

```sh
HINDSIGHT_CONFIG="$CANARY_CONFIG" \
  npx @vectorize-io/hindsight-coding-agents@0.8.0 uninstall codex claude-code
```

Sources: [ai-memory lifecycle operations at 2.5.2](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/docs/lifecycle-ops.md),
[ai-memory install at 2.5.2](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/docs/install.md),
[coding-agent config](https://github.com/vectorize-io/hindsight/blob/f9d9e2ab88bd237a81bba12f0ac5cf173aafd46c/hindsight-integrations/coding-agents/src/core/config.ts),
[installer](https://github.com/vectorize-io/hindsight/blob/f9d9e2ab88bd237a81bba12f0ac5cf173aafd46c/hindsight-integrations/coding-agents/src/installer.ts),
[Colima 0.10.3](https://github.com/abiosoft/colima/releases/tag/v0.10.3).
