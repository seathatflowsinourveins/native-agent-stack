# Native vector-state recovery

On September 19, 2026, Qdrant **1.19.1** produced a native full-storage snapshot.
Restic **0.19.1** encrypted that snapshot, checked every stored pack, and restored
the archive. A separate Qdrant process then loaded the recovered archive using
the upstream `--storage-snapshot` option. The active instance was not replaced.

Direct results from the native commands and independently repeated API checks:

| Check | Result |
| --- | --- |
| Native full snapshot | 6,960,640 bytes; checksum matched native creation response |
| Restic backup and verified restore | One file; all 6,960,640 bytes identical |
| `restic check --read-data` | 2 snapshots, 4/4 packs; `no errors were found` |
| Recovered collections | 5/5 green; 201/201 points |
| Code retrieval collection | 139 points; named dense vectors, 2,048 dimensions |
| Canonical point ID/vector/payload digests | All five collections matched before, after and in the restored instance |
| Full collection config, payload schema and aliases | Matched; both alias sets empty |
| Exact nearest-neighbor query | Same ordered five ID/version/score records; maximum score difference 0.0 |
| Cleanup | Isolated process exited 0; isolated listener closed; live instance still available |

The [receipt](receipt.json) contains sanitized results. Snapshots, code payloads,
point IDs, full query vectors, native logs and encryption passwords stay private.
An independent reviewer repeated the digest, config and exact-query checks
against the running source and restored instances before cleanup.

## Upstream workflow

These are replay templates, with operator-selected paths and a single-node
source. Full-storage snapshot restoration is a startup operation. Use a fresh
storage directory and unused loopback port; never point the recovery process at
the live storage directory. Provision `RESTIC_REPOSITORY`,
`RESTIC_PASSWORD_FILE` and a private cache through the native environment.
The demonstrated repository was separate from the earlier public-file drill.

```bash
curl --fail-with-body --silent --show-error --max-time 60 \
  --request POST "$QDRANT_URL/snapshots" --output "$PRIVATE_RUN/native-create.json"
# Select the exact returned result.name and validate that it is a plain filename.
curl --fail-with-body --silent --show-error --max-time 60 \
  "$QDRANT_URL/snapshots/$SNAPSHOT_NAME" --output "$PRIVATE_RUN/full.snapshot"
sha256sum "$PRIVATE_RUN/full.snapshot"
# Compare size and SHA256 with result.size and result.checksum in native-create.json.

# Working directory: PRIVATE_RUN. Restic init is needed only for a new repository.
restic backup full.snapshot --host native-agent-stack-state --tag qdrant-state --json
restic check --read-data
restic restore "$RESTIC_SNAPSHOT_ID" --target "$PRIVATE_RUN/encrypted-restored" \
  --verify --overwrite never --json

qdrant --config-path "$PRIVATE_RUN/isolated.yaml" \
  --storage-snapshot "$PRIVATE_RUN/encrypted-restored/full.snapshot" \
  --disable-telemetry
```

The isolated configuration uses distinct `storage.storage_path` and
`storage.snapshots_path`, `service.host: 127.0.0.1`, an unused `service.http_port`,
`service.grpc_port: null`, and `cluster.enabled: false`. **Omit
`storage.temp_path` for this tested full-storage restore.** An initial attempt
with one explicit temporary directory failed with exit 101: the outer archive
and nested collection extraction collided on `config.json`. The
[v1.19.1 implementation](https://github.com/qdrant/qdrant/blob/v1.19.1/src/snapshots.rs)
explains why leaving the temporary path unset separates these extraction areas.
Recovery used a new directory; no force option or live overwrite was used.

Use native `GET /collections`, `GET /collections/{name}` and
`POST /collections/{name}/points/scroll` with payloads and vectors to compare
logical state; canonicalize complete point records, not just counts. Also compare
the complete `config`, `payload_schema` and `GET /aliases` responses. The recorded
query used `POST /collections/{name}/points/query`, a retained dense vector,
`using: "dense"`, `params: {"exact": true}`, `limit: 5` and `with_payload: false`.
An initial request passed the named-vector object instead of its numeric array
and returned HTTP 400; the corrected upstream shape succeeded. This query
checks recovery equivalence, not semantic retrieval quality.

## Scope

This was one same-host recovery drill with sequential cross-collection checks,
not a globally atomic database transaction or an off-host disaster recovery.
The encrypted repository and its password still share a host. No independent
key escrow, backup schedule or retention deletion was enacted. SocratiCode's
live MCP client was not rebound to the replacement database. Optional static UI
assets were absent from the native binary installation; the HTTP API was tested.
No model inference, trading execution or provider token saving is implied.

Primary references: [Qdrant snapshots](https://qdrant.tech/documentation/snapshots/),
[snapshot workflow](https://qdrant.tech/documentation/tutorials-operations/create-snapshot/),
[query API](https://api.qdrant.tech/api-reference/search/query-points), and
[Restic restore](https://restic.readthedocs.io/en/stable/050_restore.html).
