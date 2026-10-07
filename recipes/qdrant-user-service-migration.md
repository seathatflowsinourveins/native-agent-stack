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

## Pending recovery verification

The patch-version compatibility contract does not close these limits:

- **PENDING: storage-format and WAL differences.** Retain a review of the
  pinned [1.19.1-to-1.19.2 source comparison](https://github.com/qdrant/qdrant/compare/6ab21cac18ebb6f4ae29102c7f8f5cc11affd5de...016542aa5deb6c66380bb137badf73d54f742bde)
  and the [1.19.2 release notes](https://github.com/qdrant/qdrant/releases/tag/v1.19.2).
  The review must address storage-format changes, WAL/flush ordering and
  recovery behavior relevant to this snapshot route, with file/line
  citations and an explicit compatibility conclusion before execution ACK.
  A supported snapshot route is not permission to open the target's state
  in place with the older binary.
- **PENDING: interrupted recovery and a second invocation.** Close this with
  retained review of the pinned
  [target recovery failure paths](https://github.com/qdrant/qdrant/blob/016542aa5deb6c66380bb137badf73d54f742bde/src/snapshots.rs#L145)
  and relevant unchanged upstream tests, or a CC-authorized isolated
  rehearsal using supported Qdrant commands. Retain the exact inputs,
  interruption point, returned state and inventory checks. Label upstream
  test evidence and local rehearsal evidence separately; neither is a host
  restore receipt. The ordinary successful-start sequence below does not
  establish safe replay into a partially recovered target.

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
with reviewed absolute paths. **Before recovery, explicitly repin the
ordinary base unit's `ExecStart` to the adopted 1.19.2 binary**, for example
`/ABSOLUTE/STACK_HOME/tools/qdrant-1.19.2/qdrant`. The historical example
names 1.19.1; replacing its absolute placeholders alone does not repin it.
Use the same config path, working directory and owned storage paths for
ordinary startup and the recovery override. The ordinary base argv must
contain no snapshot-recovery arguments.
Use **new, empty, separately owned native
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

If recovery fails or is interrupted, stop and disable the owned native unit
using the rollback entry below, and preserve the partial target, snapshot
and returned failure evidence. Do not start that partial target ordinarily,
retry recovery into it or add `--force-snapshot` as a workaround. Return to
the preserved source with its rollback checks; any subsequently authorized
restore attempt uses new, empty, separately owned target state. The pending
failure-path limit above must be resolved before allowing any other retry
policy.

Wait for native HTTP readiness and the complete restored collection/alias
inventory before treating recovery as complete. A Type=simple unit being
active or `start` returning zero is insufficient. Retain the returned state,
stop the owned unit, remove only the recovery drop-in, `daemon-reload`, and
verify the effective base `ExecStart` **before** starting the ordinary unit:

```sh
systemctl --user show native-stack-qdrant.service -p ExecStart
```

Require the adopted 1.19.2 binary, the same config/storage paths and no
snapshot-recovery arguments. Then start the ordinary canonical unit and
record `systemctl --user show native-stack-qdrant.service -p ExecStart -p MainPID`.
Inspect that owned running process's actual argv, for example its
`/proc/<MainPID>/cmdline`, and require the same version/path checks with no
`--storage-snapshot` or other recovery argument. Fail the gate before
releasing writers if the effective unit or process selects 1.19.1.
Ordinary starts must not repeat recovery.
Enable the user unit only after its gates pass.

Sources: [target CLI recovery](https://github.com/qdrant/qdrant/blob/016542aa5deb6c66380bb137badf73d54f742bde/src/main.rs#L249),
[target recovery staging](https://github.com/qdrant/qdrant/blob/016542aa5deb6c66380bb137badf73d54f742bde/src/snapshots.rs#L145),
[systemd@v259 Type=simple](https://github.com/systemd/systemd/blob/v259/man/systemd.service.xml#L164),
[ExecStart reset](https://github.com/systemd/systemd/blob/v259/man/systemd.service.xml#L395),
[Linux process argv](https://www.kernel.org/doc/html/latest/filesystems/proc.html#process-specific-subdirectories),
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

Keep every writer quiesced for either rollback branch. If the native target
has received new writes, including integration metadata, preserve and verify
a fresh native full snapshot while its endpoint is still available; record
the current inventory and known-answer expectation for that snapshot. The
old source volume is then stale. If a fresh snapshot cannot be verified,
preserve both stores, report the gap and keep writers quiesced; do not
restore service from the stale volume.

At entry to **either** rollback branch, persistently disable and stop the
native unit before restoring the original service arrangement:

```sh
systemctl --user disable --now native-stack-qdrant.service
systemctl --user show native-stack-qdrant.service -p ActiveState -p UnitFileState
```

Retain both commands' exit codes and returned output. Require successful
disablement and an explicit read-back of `ActiveState=inactive` and
`UnitFileState=disabled` before starting a rollback service. A stopped but
enabled unit could reopen the abandoned store when the user manager starts.

- **Before new native writes:** restart the preserved owned rootless
  container on its original port and preserved volume.
- **After new native writes:** restore the verified fresh snapshot into a
  **separate fresh rootless rollback volume**, with a compatible release and
  one-time recovery discipline. Do not assume a 1.19.2 snapshot restores
  into 1.19.1, or start the stale original volume as the current source.

For either branch, require rollback-service HTTP readiness, the recorded
complete collection/alias inventory, vector configurations and point counts,
and the same actual known-answer retrieval check before releasing writers.
Compare against the quiesced original source before new writes, or against
the fresh native snapshot's recorded inventory and oracle after new writes.
Keep writers quiesced through restore and revalidation. Retain the preserved
source, partial target if any, and rollback stores until their owner retires
them.

Sources: [snapshot compatibility](https://qdrant.tech/documentation/operations/snapshots/),
[SocratiCode@f6191f0 watcher modes](https://github.com/giancarloerra/socraticode/blob/f6191f076a42405f0d5508139f3a8b505cfef93a/src/services/watcher.ts#L593),
[startup off control](https://github.com/giancarloerra/socraticode/blob/f6191f076a42405f0d5508139f3a8b505cfef93a/src/services/startup.ts#L56),
[startup incremental update](https://github.com/giancarloerra/socraticode/blob/f6191f076a42405f0d5508139f3a8b505cfef93a/src/services/startup.ts#L299),
[pre-scan metadata write](https://github.com/giancarloerra/socraticode/blob/f6191f076a42405f0d5508139f3a8b505cfef93a/src/services/indexer.ts#L1657),
[systemctl disable, --now and property read-back](https://www.freedesktop.org/software/systemd/man/latest/systemctl.html),
[user-manager default target](https://www.freedesktop.org/software/systemd/man/latest/systemd.special.html#default.target1),
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

## Dated dependency limit (2026-10-07): consolidation gateway

From2026-10-07T01:47Z, CC review
`review-ns2604-coop-20261007T015759Z` reports degraded ai-memory consolidation
and auto-improve calls on21128: about one in four to one in three Sol calls
succeeds until the owner's pool decision. The reported cause is one free-plan
ChatGPT connection in the nine-connection Codex pool without Sol entitlement;
chat/Responses requests landing there can return400, while reported upstream8307
sibling fallback covers images. The bounded01:47–01:52Z sample reports six Sol
rows, four landing there, three explicit400s and one explicit200 elsewhere;
unspecified outcomes are not inferred. Locators: that CC review, dispatch
`task-ns2604-coop-20261007T014716Z`, and its allowlisted21128
`/api/usage/call-logs` observations. This lane's count was canceled and not run.

The [composition decision](../docs/decisions/2026-10-05-omniroute-gateway-composition.md)
retains `cx/gpt-6.1-sol-max`; no model or alias change is needed. The pool
choice/configuration belongs to the owner/CC, not this migration recipe or lane.
The23:47Z C2X PASS stands as one run, not later steady-state acceptance. This is
**a dated dependency limit, not a new Qdrant gating row**. It does not establish
or alter the unexecuted native migration, qualify recovery limits, or authorize
route edits, a second smoke, or access to decrypted-settings endpoints.
