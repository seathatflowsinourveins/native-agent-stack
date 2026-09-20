# Native WSL memory maintenance

Official ai-memory **2.3.2** passed one isolated Linux x86_64 trial on WSL2 on
September 20, 2026: **65 checks, 39 native MCP tool calls**, restart persistence,
native HTTP backup, and native restore into an empty synthetic store. All four
owned server processes exited 0 without forced termination. The selected results
are in [receipt.json](receipt.json) and [native-facts.json](native-facts.json).

This qualifies the synthetic native workflow. It does **not** establish a live
WSL service, Codex/Claude registration, production data migration, embeddings,
provider usage, or whole-machine confinement. No global installation, production
state, authentication store, client configuration, or existing service was used
or changed. Model/provider features were disabled; no history was ingested.

## Frozen acceptance

Before native execution, the runner copied and hashed its exact source,
[pins](pins.json), [configuration](config.toml), and [oracle](oracle.json). It
verified the official archive, release checksum sidecar, extracted executable,
and bundled MIT license. Only the executable and license were extracted; bundled
hooks, service definitions, and installers were not installed.

The synthetic alpha/beta projects cover exact scoped bodies, positive lexical
FTS, cross-project query negatives, explicit not-found read errors, reserved Git
path rejection, a five-byte Unicode directory component, replacement of an old
marker, and persistence after shutdown/restart. The test makes explicit scoped
requests; project routing is not a tenant-authorization boundary.

The native `backup` command is an HTTP client. The runner starts a separate
server against its owned store on an OS-selected loopback port, authenticates
with a private per-run bearer, and explicitly sets `AI_MEMORY_SERVER_URL` for the
backup client. It retains the resulting native archive, verifies its wiki bytes
and SQLite snapshot, then sends SIGINT only to that owned server PID and waits
for exit 0. Native `restore --from` opens a new empty target with no `--force` or
process-guard bypass. The restored server repeats the scoped retrieval checks.
This is a native-generated backup and native restore, not a constructed archive.

The restart, backup snapshot, restored store, and final original store all report
SQLite integrity `ok`, V62 present, populated page validity windows, four page
versions, and zero rows in sessions, observations, workstream events, native
workstream sessions, and page embeddings. No model files appeared. All three
stdio processes advertise the same 23 tools, including the four required memory
tools. No sibling-process refusal occurred in this run; a future refusal is a
blocked restore, never permission to stop another process or bypass the guard.

## Reproduce deliberately

Use a reviewed Linux x86_64 host and a **new private directory outside Git**.
Acquire the official archive and sidecar at the URLs in `pins.json`, preserving
both files. The runner checks their exact pinned digests and does not download
or install anything. Python 3.12+ standard library is sufficient; the recorded
run used Python 3.12.3 and WSL2 kernel 6.18.33.2.

```sh
python3 blueprints/convergence-practice/wsl-memory-maintenance/run.py \
  --run-dir "$NEW_PRIVATE_RUN_DIRECTORY" \
  --archive "$REVIEWED_LINUX_ARCHIVE" \
  --sidecar "$REVIEWED_LINUX_CHECKSUM_SIDECAR"
```

The run directory must not exist and its parent must exist. The real HOME is
preserved. Child environment credentials are not forwarded; explicit data/config
paths and disabled capture/maintenance/provider features bound the intended
operations. This is not an OS filesystem or network sandbox. Only owned PIDs
are stopped; absence of arbitrary descendants is not claimed. Full protocol,
stderr, CLI results, archive, and synthetic state remain private. Public selected
facts preserve relevant outcomes; hashes are provenance, not independent proof
that historical execution occurred.

Offline checks do not launch native processes or consume model allowance:

```sh
python3 blueprints/convergence-practice/wsl-memory-maintenance/audit.py
python3 -m unittest tests.test_wsl_memory_maintenance -v
python3 scripts/validate_convergence.py \
  blueprints/convergence-practice/wsl-memory-maintenance/experiment.json --root . --json
```

## Subsequent deployment is separate

A coordinator may reuse the qualified official binary after verifying its hash.
[config.toml](config.toml) disables embedding generation, startup backfill,
assistant capture, session-end consolidation, autowire, scheduled improvement,
and background maintenance. It retains approval for explicit improvement.
Changing these choices requires the corresponding acceptance; lexical acceptance
does not qualify an embedding provider or automatic capture.

The supported server form is:

```sh
ai-memory --data-dir "$OWNED_SERVICE_DATA" --config "$OWNED_SERVICE_CONFIG" \
  serve --transport http --bind "127.0.0.1:$SELECTED_PORT" --no-watcher \
  --workspace "$EXPLICIT_WORKSPACE" --project "$EXPLICIT_PROJECT"
```

Use a coordinator-owned bearer through native `AI_MEMORY_AUTH_TOKEN`; do not reuse
the trial token or publish it. HTTP clients target the selected loopback server's
`/mcp` route with `Authorization: Bearer …`. The thin native backup client instead
receives `AI_MEMORY_SERVER_URL=http://127.0.0.1:$SELECTED_PORT` plus its native
bearer setting. Keep each host's loopback local to that host. The trial did not
install or test a user service, native-client reconnect, desktop session bus,
remote forwarding, or an active Codex/Claude memory route.

Production service creation, credentials, client registration, and restart
acceptance belong to the coordinator. Preserve this isolated prefix as evidence;
rollback for this trial is retiring only its owned files after retention needs
are met. No model calls or token savings were measured. Whole-task parent/child
provider usage remains unknown.

## Primary sources

- [Official v2.3.2 release](https://github.com/akitaonrails/ai-memory/releases/tag/v2.3.2), verified as latest on September 20.
- [Pinned CLI flags](https://github.com/akitaonrails/ai-memory/blob/353841d91618d20b110b208de284a74d0b960379/crates/ai-memory-cli/src/cli.rs).
- [Native backup HTTP client](https://github.com/akitaonrails/ai-memory/blob/353841d91618d20b110b208de284a74d0b960379/crates/ai-memory-cli/src/commands/backup.rs).
- [Native restore checks](https://github.com/akitaonrails/ai-memory/blob/353841d91618d20b110b208de284a74d0b960379/crates/ai-memory-cli/src/commands/restore.rs) and [sibling-process guard](https://github.com/akitaonrails/ai-memory/blob/353841d91618d20b110b208de284a74d0b960379/crates/ai-memory-cli/src/process_guard.rs).
- [Native endpoint and auth resolution](https://github.com/akitaonrails/ai-memory/blob/353841d91618d20b110b208de284a74d0b960379/crates/ai-memory-cli/src/http_client.rs) and [MIT license](https://github.com/akitaonrails/ai-memory/blob/353841d91618d20b110b208de284a74d0b960379/LICENSE).
