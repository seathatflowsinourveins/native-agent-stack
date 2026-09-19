# Application-state recovery

Both native recovery chains passed on September 19, 2026, with independent
verification before acceptance:

| State | Upstream chain | Accepted result |
| --- | --- | --- |
| [ai-memory](memory/README.md) | `ai-memory backup` → `restic backup/check/restore` → isolated `ai-memory restore` | 324 files recovered; SQLite integrity, 56 table counts and FTS checks matched |
| [Qdrant](qdrant/README.md) | Native snapshot API → `restic backup/check/restore` → `qdrant --storage-snapshot` | 5 collections, 201 points, all configs/payloads/vectors and one exact query matched |

These extend the earlier [22-file public-reference recovery](../hosting/backup/README.md)
to actual private application state. Public receipts contain only sanitized
results and native commands. Raw database archives, keys and private code are
not distributed.

The repository, source and password still share the host. An independently
recoverable key and an approved off-host destination are required before this
becomes a disaster-recovery design. No backup schedule or deletion policy is
silently enabled. The restored services were not selected by live MCP clients;
application process startup/query and SQLite-store recovery are the demonstrated
boundaries. State captured sequentially across databases/files is not a globally
atomic trading or agent transaction.
