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

## Proposed target and retained fallback

The proposed migration source is the indexed Qdrant 1.19.1 store; target is
the official stable 1.19.2 release, subject to the owner's ACK. Its release
notes name flush-consistency, write-tearing and recovery fixes relevant to
this operation. Release age alone does not establish quality, and these
fixes do not establish that the existing store is corrupted.

| Role | Official release | Linux musl archive SHA256 | Bytes |
| --- | --- | --- | ---: |
| Proposed target | [1.19.2](https://github.com/qdrant/qdrant/releases/tag/v1.19.2), published 2026-10-05T14:16:50Z | `50b253243309ed0ae50a19f678f0d0adcc4f0b567b3bd2c5c0c7e02fa8404bb6` | 33015429 |
| Retained catalog/B fallback | [1.19.1](https://github.com/qdrant/qdrant/releases/tag/v1.19.1) | `70a40529e2ebe0a2787d574d3a2e28437cfe94f26f24fa419f6ac57b4ae817c9` | 32315868 |

The archive is `qdrant-x86_64-unknown-linux-musl.tar.gz`; use the selected
release's official asset and retain its upstream license. The target hash
comes from the [release-assets API](https://api.github.com/repos/qdrant/qdrant/releases/tags/v1.19.2).
This proposal updates neither the catalog nor active installation.

The B files are pre-execution alternative pin choices requiring new, empty
native state. They must never open state already recovered or populated by
1.19.2; operational rollback uses the separate preserved source or a fresh
compatible restore described below.

The [official snapshot compatibility contract](https://qdrant.tech/documentation/snapshots/#restore-snapshot)
permits the same minor version with target patch at least the source patch.
Thus 1.19.1-to-1.19.2 is an upstream-supported format route. Full-storage
recovery remains the CLI startup operation; target
[`016542aa5deb6c66380bb137badf73d54f742bde`](https://github.com/qdrant/qdrant/blob/016542aa5deb6c66380bb137badf73d54f742bde/src/main.rs#L249)
retains it. Source compatibility is not an executed restore or retrieval
qualification: those gates remain required after ACK.

## Preserve the whole owned store

Use the supported **full-storage snapshot** for a standalone store.
Collection snapshots alone omit aliases and may miss SocratiCode's metadata
and graph collections. Verify standalone mode with `GET /cluster`; this
CLI recovery procedure does not apply to a distributed cluster.

1. Quiesce every writer, including background startup indexing and watchers.
   Use the acceptance controls below before any owned process connects.
   Drain already-running indexing; no foreground call is not proof of idle
   background work. Record version/commit,
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
unset. At the reviewed source and target pins, full-unpack and collection
staging locations are derived from the owned storage paths.

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
ExecStart=/ABSOLUTE/STACK_HOME/tools/qdrant-1.19.2/qdrant --config-path /ABSOLUTE/CONFIG/qdrant.yaml --disable-telemetry --storage-snapshot /ABSOLUTE/SNAPSHOTS/verified.snapshot
```

Wait for native HTTP readiness and the complete restored collection/alias
inventory before treating recovery as complete. A Type=simple unit being
active or `start` returning zero is insufficient. Retain the returned state,
stop the owned unit, remove only the recovery drop-in, `daemon-reload`, and
start the ordinary canonical unit. Ordinary starts must not repeat recovery.
Enable the user unit only after its gates pass.

Sources: [target CLI recovery](https://github.com/qdrant/qdrant/blob/016542aa5deb6c66380bb137badf73d54f742bde/src/main.rs#L249),
[target recovery staging](https://github.com/qdrant/qdrant/blob/016542aa5deb6c66380bb137badf73d54f742bde/src/snapshots.rs#L145),
[systemd@v259 Type=simple](https://github.com/systemd/systemd/blob/v259/man/systemd.service.xml#L164),
[ExecStart reset](https://github.com/systemd/systemd/blob/v259/man/systemd.service.xml#L395),
[systemd resource control](https://www.freedesktop.org/software/systemd/man/latest/systemd.resource-control.html).

## Acceptance and rollback

Before releasing writers, retain:

- The executed 1.19.2 archive checksum, restored source/target versions and
  startup outcome. A matching release-API digest alone is source review.
- Native version/commit, active user-unit state and its actual process.
- Complete collection/alias inventory, each vector configuration and point
  count compared with the quiesced source. Include metadata/graph collections.
- Native `codebase_health`, `codebase_status`, and the actual expected-file
  result from `codebase_search` through an owned MCPorter config. Preserve
  exact model/dimensions, `query: ` / `passage: ` prefixes and collection prefix.
  HTTP/version checks do not establish functional retrieval.
- An ordinary unit restart followed by the same known-answer search.
  Retain failures and usage; unknown usage stays null.

Verify startup quiescence too: retain collection/metadata inventories before
and after connecting a fresh owned acceptance process. Investigate unexpected
changes; a read-like tool name does not prove that process startup was read-only.

Use the [semantic-search recipe](README.md#local-semantic-code-search).
Client configuration stays with its authorized owner. Set both supported
controls in **every owned acceptance process before its initial connection**:

```json
{
  "SOCRATICODE_AUTO_RESUME": "off",
  "SOCRATICODE_WATCHER": "manual"
}
```

Manual mode alone suppresses watcher startup but still permits background
startup incremental indexing, including metadata writes before scanning.
`SOCRATICODE_AUTO_RESUME=off` returns before startup Docker/Qdrant access and
overrides an explicit resume-project list. Already-retained processes keep
their original environment: drain existing indexing and stop owned watchers
on their verified connections, then recreate affected owned acceptance
connections with both settings. Do not stop a global MCPorter daemon serving
other owners, or use cross-process SIGTERM as a presumed batch checkpoint.
Keep these controls throughout the quiesced snapshot/restore and validation.
Production-client startup policy remains the client's owner's decision.

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
[startup off control](https://github.com/giancarloerra/socraticode/blob/f6191f076a42405f0d5508139f3a8b505cfef93a/src/services/startup.ts#L56),
[startup incremental update](https://github.com/giancarloerra/socraticode/blob/f6191f076a42405f0d5508139f3a8b505cfef93a/src/services/startup.ts#L299),
[pre-scan metadata write](https://github.com/giancarloerra/socraticode/blob/f6191f076a42405f0d5508139f3a8b505cfef93a/src/services/indexer.ts#L1657),
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
