# Native synthetic application-state recovery

[Run 35541091430](https://github.com/seathatflowsinourveins/native-agent-stack/actions/runs/35541091430)
passed at commit `2e7b4624b85a828be11752238e2806efa420ba3c` on September 20, 2026.
It created public synthetic ai-memory 2.3.2 and Qdrant 1.19.1 state on one hosted
runner, transferred exact native backups through Restic 0.19.1, and restored them
into empty application targets on a distinct hosted runner. Native post-restore
queries passed. The [receipt](../../receipts/native-offhost-app-state-20260920.json)
records the accepted scope and independent audit.

## Evidence types and returned results

| Evidence | Actual result | Scope |
| --- | --- | --- |
| Unchanged ai-memory upstream backup tests | 4 passed; 0 failed/ignored | Native administrative gzip backup, seeded content, empty store and symlink behavior |
| Unchanged ai-memory upstream restore tests | 6 passed; 0 failed/ignored or semantic skips | Expected paths, unsafe/link rejection and a real GNU sparse SQLite round trip |
| Unchanged Qdrant upstream snapshot tests | 4 passed; 0 failed/skipped | Two original tests with both on-disk-vector settings, targeting the verified release binary |
| Restic local integration | Full data check passed; wrong key rejected with exit 12 and no restored files; exact snapshot restore/verification passed | Two native archives, 216,461 total bytes; ciphertext unchanged |
| ai-memory local integration | Native restore exit 0; 14 destination MCP tool calls matched expectations | Three exact page bodies, own-scope hits, cross-scope refusals/empty searches, stale-term absence and status |
| Qdrant local integration | All 10 points, vectors and payloads plus configuration, indexes and alias matched | Dense, Berlin-filtered and sparse queries matched source and frozen expectations through both collection and alias |

The three test invocations were:

```sh
cargo test --locked -p ai-memory-mcp --lib integration::admin_backup:: -- --nocapture
cargo test --locked -p ai-memory-cli --lib commands::restore::tests:: -- --nocapture
uv --project "$OWNED_RUN/upstream-qdrant/tests" run --no-sync --offline pytest   "$OWNED_RUN/upstream-qdrant/tests/openapi/test_snapshot.py::test_collection_snapshot_operations"   "$OWNED_RUN/upstream-qdrant/tests/openapi/test_snapshot.py::test_full_snapshot_operations"   -v -p no:cacheprovider --junitxml "$OWNED_RUN/raw/qdrant-upstream.xml"
```

Their actual stdout is retained in [backup](source/memory-upstream-backup.stdout),
[restore](source/memory-upstream-restore.stdout) and
[Qdrant](source/qdrant-upstream-tests.stdout), with [JUnit](source/qdrant-upstream.xml).
The source pins are ai-memory `353841d91618d20b110b208de284a74d0b960379` and
Qdrant `6ab21cac18ebb6f4ae29102c7f8f5cc11affd5de`. The
[upstream selection](../../../blueprints/convergence-practice/offhost-app-state/upstream.json)
binds test files, release binaries and toolchains. The Qdrant helper's unchanged
all-interface HTTP listener ran inside a separate network namespace containing
only loopback. This was a selected release-target test run, not full upstream CI.

The separate cross-host composition is authored in this repository. Its
[frozen plan](../../../blueprints/convergence-practice/offhost-app-state/plan.json)
binds 12 execution inputs; its synthetic memory fixture reuses the accepted WSL
maintenance recipe, and its Qdrant fixture reuses the unchanged public ten-point
upstream helper. The full-storage restore and query assertions extend beyond what
the upstream full-snapshot create/list/delete test exercises.

## Native recovery and observation

[Selected commands](selected-commands.json) preserve actual command arrays,
time bounds, return codes and links to full records. Native operations included
Restic `check --read-data` and exact `restore --verify --overwrite never`,
ai-memory `restore --from`, and Qdrant `--storage-snapshot` on an empty target.
Snapshot `0fd4395da35e8ebde5335c0985e349cab7f81f6491c49e102dffbeb87d791134`
contained the native memory archive and Qdrant snapshot identified in
[source facts](transfer/source.json); their hashes matched after transfer.

[Source](source/source.json) and [destination](destination/destination.json)
records contain different boot-identity hashes, the same workflow run/head and
separate job identities. The fixture-only Actions secret reached each job
separately; no key accompanied the transfer. Both jobs remain in the same GitHub
administrative domain, so this is not account-loss or independent-provider recovery.

An independent reviewer verified all three original artifact ZIP/API digests,
restored both raw-proof repositories and the exact transfer using native Restic,
and reconciled 144 raw/public command-stream hash associations and all 12 frozen
source hashes. The reviewer checked the actual [14 MCP calls](destination/memory-query-facts.json)
and Qdrant response bytes against source and fixed expectations. Dense results
were IDs `8,3,6,7,5,2,4,1`; Berlin filtering returned `3,2,1`; sparse search
returned ID `9` with score `0.5`, through both the collection and its alias.

The restored source archive's SQLite integrity was `ok`, migration 62 was present,
all four page versions had windows, and event/history/embedding tables were empty.
Destination SQLite equality is the runner's composed assertion. Independently
observed destination memory evidence is the native MCP output, not a second live
database query by the reviewer. The reviewer did not rerun tests or start services.

Both jobs retained native process exit/listener closure and successful
[cleanup](destination/cleanup.json): temporary password, owned runtime and prior
unencrypted raw evidence removed; encrypted proof and selected reports retained.

## Publication and limits

[Projection manifest](projection-manifest.json) binds every selected hosted member
to its committed bytes. Most copies are byte-identical to the already sanitized
hosted reports. Five report projections additionally replace symbolic password-file
locations or opaque synthetic result identifiers with declared aliases. Semantic
page paths/bodies and returned query values remain intact. Embedded `raw_sha256`
identifies original native streams; `public_sha256` and `public_path` identify the
hosted report namespace, which includes omitted files. Neither should be confused
with a further projected file's publication hash.

Encrypted proof repositories, repository envelopes, complete native archives,
private keys/authentication material and incidental build/service streams are not
committed here. Hashes retain their evidence identities without publishing them.
No private password content or concrete private-key location was inspected to
prepare this publication.

Acceptance covers newly created synthetic state and sequential application
snapshots. It does not establish atomic cross-application recovery, restoration
of old private backups, production or whole-stack disaster recovery, native-client
rebinding, reboot, external alerting or unattended hosting. There were no model,
provider or broker calls. Token/cost savings are unmeasured, represented as null.
