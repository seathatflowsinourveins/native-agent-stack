# Move an owned Qdrant store to its native user service

This recipe closes the lifecycle gap between an ad hoc Qdrant container and
the catalog's official binary plus systemd user unit. It serves foundation
code navigation for the research and historical-simulation stack. It does
not select a memory product or qualify a retrieval model.

Reuse [native-stack-qdrant.service.example](../examples/native-stack-qdrant.service.example)
and [qdrant.yaml.example](../examples/qdrant.yaml.example): state stays outside
the versioned binary prefix, the service binds to loopback, and telemetry
and gRPC are disabled.

This is a **source-reviewed migration procedure**, not a new host recovery
receipt. A host that requires review/ACK obtains it before downloading,
snapshotting, restoring, or applying a unit. Keep the original service
available until the reviewed cutover window.

## Pin and currency

The catalog names Qdrant 1.19.1 and its official
[Linux musl release archive](https://github.com/qdrant/qdrant/releases/tag/v1.19.1),
SHA256 `70a40529e2ebe0a2787d574d3a2e28437cfe94f26f24fa419f6ac57b4ae817c9`.
Retain the upstream license beside the binary; follow the
[existing archive recipe](README.md).

A currency read on 2026-10-06 found stable 1.19.2, published
2026-10-05T14:16:50Z. Requested 1.19.1 is within 180 days, but is no longer
latest. [Upstream 1.19.2 notes](https://github.com/qdrant/qdrant/releases/tag/v1.19.2)
include flush-consistency, storage write-tearing and restart-recovery fixes.
The owner explicitly settles patch adoption before migration is ACKed.
This procedure keeps the requested same-version 1.19.1 path concrete; it
does not silently change the pin or establish current corruption.

## Preserve the whole owned store

Use the supported **full-storage snapshot** for a standalone store.
Collection snapshots alone omit aliases and may miss SocratiCode's metadata
and graph collections. Verify standalone mode with `GET /cluster`; this
CLI recovery procedure does not apply to a distributed cluster.

1. Quiesce every writer, including automatic watchers. Record version/commit,
   all collection names, aliases, vector configurations and point counts.
   Keep writers quiesced through validation/cutover. Full snapshots assemble
   collections sequentially; continuing writes do not produce an atomic
   cross-collection checkpoint.
2. Create `POST /snapshots?wait=true`. Retain the returned name, size and
   checksum. Download that returned name with `GET /snapshots/{name}` into
   an owned disk directory.
3. Verify bytes against the returned checksum when present and retain their
   local SHA256. A missing server checksum is a verification gap, not a
   server-verified download. Do not guess a name or reuse an older snapshot.
4. Budget disk for the original store, source-generated snapshots, download,
   unpacked staging and new storage. A generic collection-restore 2× estimate
   does not cover this entire migration. Keep scratch out of shared `/tmp`.

Sources: [Qdrant snapshots](https://qdrant.tech/documentation/operations/snapshots/),
[full-snapshot API](https://api.qdrant.tech/api-reference/snapshots/create-full-snapshot),
and [Qdrant@6ab21ca full-storage implementation](https://github.com/qdrant/qdrant/blob/6ab21cac18ebb6f4ae29102c7f8f5cc11affd5de/lib/storage/src/content_manager/snapshots/mod.rs#L122).

## First start and ordinary starts

After ACK, install the official archive and render the existing examples
with reviewed absolute paths. Use **new, empty, separately owned native
state**. Do not point the binary at Docker's internal volume directory.
Set the reviewed HTTP port, for example 21633; keep `storage.temp_path`
unset. At 1.19.1, default full-unpack and collection-staging locations are
derived from the owned storage paths.

Apply the reviewed CPU policy: a user unit may set
`Slice=background.slice` and `Nice=19`; the embedding service retains its
separate reviewed weight. Use the user manager and `daemon-reload`.
No daemon-reexec or operating-system restart is needed.

Stop only the owned rootless source container at cutover. Retain its
container, volume and image. On the native unit's first start, add the
supported recovery argument:

```text
qdrant --config-path /ABSOLUTE/CONFIG/qdrant.yaml
  --disable-telemetry --storage-snapshot /ABSOLUTE/SNAPSHOTS/verified.snapshot
```

Omit `--force-snapshot`. A first-start systemd drop-in clears inherited
`ExecStart` and replaces it with the canonical argv plus that argument:

```ini
[Service]
ExecStart=
ExecStart=/ABSOLUTE/STACK_HOME/tools/qdrant-1.19.1/qdrant --config-path /ABSOLUTE/CONFIG/qdrant.yaml --disable-telemetry --storage-snapshot /ABSOLUTE/SNAPSHOTS/verified.snapshot
```

Wait for native HTTP readiness and the complete restored collection/alias
inventory before treating recovery as complete. A Type=simple unit being
active or `start` returning zero is insufficient. Retain the returned state,
stop the owned unit, remove only the recovery drop-in, `daemon-reload`, and
start the ordinary canonical unit. Ordinary starts must not repeat recovery.
Enable the user unit only after its gates pass.

Sources: [pinned CLI recovery](https://github.com/qdrant/qdrant/blob/6ab21cac18ebb6f4ae29102c7f8f5cc11affd5de/src/main.rs#L249),
[recovery staging](https://github.com/qdrant/qdrant/blob/6ab21cac18ebb6f4ae29102c7f8f5cc11affd5de/src/snapshots.rs#L145),
[systemd resource control](https://www.freedesktop.org/software/systemd/man/latest/systemd.resource-control.html).

## Acceptance and rollback

Before releasing writers, retain:

- Native version/commit, active user-unit state and its actual process.
- Complete collection/alias inventory, each vector configuration and point
  count compared with the quiesced source. Include metadata/graph collections.
- Native `codebase_health`, `codebase_status`, and the actual expected-file
  result from `codebase_search` through an owned MCPorter config. Preserve
  exact model/dimensions, `query: ` / `passage: ` prefixes and collection prefix.
  HTTP/version checks do not establish functional retrieval.
- An ordinary unit restart followed by the same known-answer search.
  Retain failures and usage; unknown usage stays null.

Use the [semantic-search recipe](README.md#local-semantic-code-search).
Client configuration stays with its authorized owner. Require manual
SocratiCode watcher mode in owned acceptance configs throughout the quiesced
cutover; auto mode can restart watching on query/status calls. Stop the
original owner's watcher before changing the owned test config. Allow any
already-active work to finish before snapshotting or releasing writers.

Before new native writes, rollback stops the native unit and restarts the
preserved owned rootless container on its original port. After new writes,
including integration metadata, the old volume is stale: re-quiesce every
writer, preserve a fresh native full snapshot and restore into a **separate
fresh rootless rollback volume** with a compatible release and one-time
recovery discipline. Keep writers quiesced through restore and revalidation.
Retain both stores until their owner retires them. Do not assume a 1.19.2
snapshot restores into 1.19.1.

Sources: [snapshot compatibility](https://qdrant.tech/documentation/operations/snapshots/),
[SocratiCode@f6191f0 watcher modes](https://github.com/giancarloerra/socraticode/blob/f6191f076a42405f0d5508139f3a8b505cfef93a/src/services/watcher.ts#L593),
[canonical user-unit example](../examples/native-stack-qdrant.service.example).

## Organic use is a separate gate

Record BEFORE/AFTER counts with their source and observation window.
Separate native client MCP calls from owned MCPorter integration calls;
connection logs and acceptance searches are not organic use. If the client
switch has not occurred, AFTER has no valid window and stays null. Do not
infer zero from configuration alone.

A dated exclusion applies when expected-file integration cannot pass.
Otherwise retain passed integration while the client owner completes the
switch and observes real use. A host awaiting its required ACK remains
pending; source review and a draft PR are not host acceptance.
