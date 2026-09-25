# Decision: ai-memory 2.4.0 release review; no upgrade yet (2026-09-25)

**Decided by:** a Claude Code writer session for the workstation lane, wave A, on
branch `claude/workstation-lane-wave-a-20260925`. The doc was first written against
`origin/main@720e294b`. It was revised on 2026-09-25 after an independent review and a
rebase onto `origin/main@8c7b7f3b`. The new base includes #159 (`83b6f87b`), which made
ai-memory assistant capture opt-in: the Claude settings template's `stop` hook adds
`--capture-assistant` only through `${AI_MEMORY_CAPTURE_ASSISTANT}`.

**Scope:** a read-only review of
[ai-memory v2.4.0](https://github.com/akitaonrails/ai-memory/releases/tag/v2.4.0) against
the current pin, 2.3.2. It applies to host `nativestack-5975wx-20260925`. **No upgrade was
performed.** No binary, hook, configuration, service or memory store was changed. The pin in
`manifests/stack.json`, `adoption/pins-linux-x86_64.json` and the landscape winner stays 2.3.2.

## Decision

Stay on 2.3.2 until a planned upgrade window. 2.4.0 is a normal forward upgrade. It adds
two schema migrations, one security fix and new features that are off by default. It
cannot be rolled back without restoring a backup. It does not contain the query/document
embedding-prefix support this stack needs before ai-memory can use Nemotron embeddings with
prefixes: upstream PR #859 merged into `release/2.5` on 2026-09-23, after the release. If
the window's goal includes that support, target the first release that contains #859.

## Evidence (fetched 2026-09-25T14:38Z)

The review used five commands:

- `gh release view v2.4.0 --repo akitaonrails/ai-memory`
- `gh api repos/akitaonrails/ai-memory/compare/v2.3.2...v2.4.0`
- `gh api` for `docs/design-memory-aging.md` and `docs/install.md` at `ref=v2.4.0`
- `gh release list`
- `gh pr view 859`

The revision on 2026-09-25 (fetched about 15:15Z) added `gh api /advisories/<id>` for the
three advisories, `gh pr view 859 --json baseRefName`, the rmcp features in `Cargo.toml`
and `crates/ai-memory-cli/Cargo.toml` at `v2.3.2`, and `gh pr diff` for #780 and #804.

The results:

- **Release.** Published 2026-09-21T23:45:13Z. It is the latest release; nothing newer
  exists. The tag object is `5c4350e3`, and it points at commit `b1b25219`. The release is
  marked `immutable: false`. The body lists only SHA-256 checksums and install commands. The
  linux-x86_64 tarball is `590f75dd…5076`.
- **Compare.** v2.3.2 (`353841d9`) to v2.4.0 is 118 commits ahead and 0 behind, over 137
  files. `CHANGELOG.md` has a 2.4.0 section.

### Migrations

The release adds two migrations. Both are additive, and neither backfills data:

- **`V65__page_compacted_marker.sql`** adds a nullable `pages.compacted_at` column.
- **`V66__auto_improve_claim_attempts.sql`** adds `attempts`, `last_error` and
  `last_failed_at` to `auto_improve_scheduler_claims`, plus an index. Existing claims keep
  `attempts = 0`, which means "in flight". So claims leaked under 2.3.2 stay excluded; they
  are not retried.

`serve` applies migrations at startup, after writing a pre-migration safety archive of the
data directory. Migrations are forward-only. Refinery's `set_abort_missing(true)` makes an
older binary refuse a newer store with `DataSchemaAhead`
(`docs/design-memory-aging.md` "Downgrade note"; `docs/install.md` "Keeping ai-memory up to
date"). This repository's own 2.4.0 trial found the same failure from the hooks side: stock
2.3.2 hook binaries abort on a store migrated to 2.4.0
([`ai-memory-embedder-deployment.json`](../../evidence/artifacts/local-model-alignment-20260923/ai-memory-embedder-deployment.json)).

### Breaking changes and default behaviour changes

The changelog marks nothing as breaking. The MCP surface stays at 23 tools. These changes
apply without any opt-in:

- **rmcp 1.7 to 2.2.** This fixes three rmcp advisories, and only one of them affects the
  HTTP server. GHSA-9pj6-vhgr-3mwh is an unauthenticated Streamable-HTTP session-table leak
  or DoS in the server transport. On this host, `nativestack-memory.service` runs
  `serve --transport http --bind 127.0.0.1:49474`, so it applies to the transport in use.
  Exposure is limited to local processes. GHSA-9g45-5xwm-f3wc (custom HTTP headers leak to
  cross-origin redirect targets) affects rmcp's HTTP client, which 2.3.2 uses only in
  `mcp-bridge`. GHSA-33f5-2c5q-wgwj (missing resource-field validation in OAuth
  protected-resource metadata discovery) affects rmcp's OAuth support. 2.3.2 does not enable
  it: its rmcp features are `server`, `macros`, `transport-io`,
  `transport-streamable-http-server` and `schemars`, plus `client` and the reqwest
  streamable-HTTP client for the bridge.
- **Access reinforcement.** `memory_read_page`, its related-page walk and `memory_explore`
  now raise `access_count`/`last_accessed_at`, as `memory_query` already does. Pages read
  this way decay more slowly.
- **Case and Unicode collisions.** A page write is refused when another live page in the
  same project differs only by case or Unicode normalization. `reindex` skips such pairs and
  reports how many it found.
- **Capture sanitizing.** The privacy strip now also redacts secrets written as JSON,
  `Authorization: Basic`, Azure `AccountKey=`, npm `_authToken=` and Windows credential
  paths. Terminal escapes, NUL and bidi characters are removed from captured text.
- **Response and log changes.** `memory_status` gains a `scope` object with `resolved_by`.
  The server logs a warning when an unscoped MCP read resolves through the startup seed or
  the default. `memory_lint` adds advisory `contradiction` findings when embeddings exist.
- **Auto-improve.** A failed scheduled review releases its claim and retries, then parks
  after 3 attempts. The reviewer's context now excludes `sessions/` pages.
- **Pinned pages in the briefing.** A project-scoped `memory_briefing` snapshot now carries
  a bounded `pinned` list (up to 10) of the project's pinned latest pages (#780). It is
  omitted when the project has no pins, and no option turns it off. Only `memory_query`'s
  `pin_first` is opt-in.
- **Evidence count in status.** `memory_status` now reports the project's `evidence_rows`
  count. It does not change ranking.

### Configuration changes

No key is removed or renamed, and no existing configuration has to change. The new keys all
default to off, or to the old behaviour:

- `[decay] compact_cold_episodic`, default `false`.
- `[decay] dedup_cold_clusters`, default `false`, with `dedup_min_pts` and `dedup_max_eps`
  (about 0.15).
- `[decay.half_life_days]` with `working`, `episodic`, `semantic` and `procedural`. When the
  table is absent, decay uses the scalar λ as before.
- `[dream]`: `enabled` defaults to `false`. The section also has `interval_secs`,
  `idle_window_secs`, `min_pts`, `max_eps`, `max_clusters_per_run` and `min_cold_pages`,
  with environment variables such as `AI_MEMORY_DREAM__ENABLED`.
- `[retrieval] belief_authority_weight`, default `0.0`.
- `[auto_improve.scheduler.experience_entropy_filter]`, off by default.

New opt-in MCP arguments:

- `memory_query`: `answer`, `reasoning`, `pin_first` and `include_superseded`.
- `memory_read_page`: `include_related` and `related_depth`.

When `AI_MEMORY_HOME` and `$HOME` are both unset, `Config::load` now takes the operator
home from `%USERPROFILE%`, then `dirs::home_dir` (#804). The changelog motivates this with
native Windows, but the code reads `USERPROFILE` on every platform. On this host `$HOME` is
set, so the fallback does not apply.

### Restart needs

- **Server.** The server must restart to load the new binary, and migrations run at that
  start.
- **Hooks.** Hooks call the binary on each event, so the hook binary must switch in the same
  window as the service.
- **MCP clients.** Claude Code and Codex clients reconnect to the restarted HTTP server (for
  example with `/mcp`).

## What the upgrade window on this host must check

1. Before stopping anything, record the current version and schema: `ai-memory --version`
   and `ai-memory status`. Take `ai-memory backup`. This backup is the only way to roll
   back, besides the automatic pre-migration archive.
2. Bump the pin through the repository process in `manifests/stack.json`,
   `adoption/pins-linux-x86_64.json`, the landscape winner and
   `adoption/templates/claude.settings.template.json`, whose eight ai-memory hook commands
   hardcode `tools/ai-memory-2.3.2`. Verify the downloaded tarball
   against the release checksum list; the release is not immutable. A pin bump retires this
   host's ai-memory receipts, so they must be recorded again.
3. Stop `nativestack-memory.service`. Switch the service binary and the hook binaries
   together. Then re-apply the hooks with the new binary. Name each native target
   explicitly, and keep this host's existing capture choices
   (`docs/token-session-handbook.md`, "Applying the defaults on another host"):

   ```sh
   NEW=~/.local/share/codex-ecosystem/tools/ai-memory-<version>/ai-memory
   "$NEW" install-hooks --apply --agent claude-code --config-file ~/.claude/settings.json \
     --server-url http://127.0.0.1:49474
   "$NEW" install-hooks --apply --agent codex --config-file ~/.codex/hooks.json \
     --server-url http://127.0.0.1:49474
   ```

   `--apply` is idempotent, and it writes a timestamped backup next to each file. Always pass
   `--server-url`: this host's service binds `127.0.0.1:49474`, and on this machine 49374 is
   another WSL distro's default. A default or copied URL could send the hooks to the wrong
   store.

   On 2026-09-25 neither hook set on this host carried `--capture-assistant`, so both
   commands omit it. Keep that state. Per the 2.3.2 `install-hooks --help`, it adds
   `--capture-assistant` only when the flag is passed, and a re-run without it removes the flag. A host that has opted in must
   pass it again; the flag is valid only for `--agent claude-code`, and the server must also
   set `capture_assistant = true`. A bare `--apply` keeps an earlier `--no-capture-prompts`
   opt-out, the stored capture mode and the project strategy.

   Afterwards, check that every ai-memory hook command names the new binary and
   `--server-url http://127.0.0.1:49474`. Check that the events are the same as before: on
   2026-09-25 that was eight Claude Code events and seven Codex events. Review the changed
   Codex hooks through `/hooks`. Start the service again. Never leave a 2.3.2 binary pointed
   at the migrated store.
4. After the restart, confirm the following:
   - The store's applied migration version is 66; upstream bumped its schema-version pin to
     66 for this release.
   - The pre-migration archive and its `pre-migration-backup.json` receipt exist.
   - `memory_status` reports the expected `scope.resolved_by`.
   - A `memory_query` answers.
   - `reindex` reports how many case/normalization collisions it skipped.
   - Hook capture continues (the observation count rises).
5. Leave every new opt-in key off. Upstream gates `dream`, `belief_authority_weight`,
   compaction and dedup on its R2 recall evaluation.
6. If embedding prefixes are in scope, confirm that the release includes #859. Otherwise
   note that 2.4.0 has no prefix support.

## Alternatives considered

1. **Upgrade to 2.4.0 now.** Rejected for this wave. The task was read-only. The upgrade
   needs a service restart and a hook switch in the same window, and a rollback needs a
   backup restore.
2. **Wait for a release that contains #859.** This is preferred if the window also moves
   memory embeddings to Nemotron with prefixes. It avoids carrying a patch, which the laptop
   host did as a pin deviation.
3. **Stay on 2.3.2 indefinitely.** Rejected as a standing position. It keeps
   GHSA-9pj6-vhgr-3mwh on the loopback HTTP transport and GHSA-9g45-5xwm-f3wc in
   `mcp-bridge`.

## Comparison that would overturn it

Two findings would each overturn this decision:

- **Upgrade now instead of waiting.** A local process on this host is shown to reach the
  loopback transport in the way GHSA-9pj6-vhgr-3mwh describes. Or upstream publishes a 2.3.x
  advisory that 2.4.0 fixes and that is exploitable here.
- **Target a 2.4.x release instead of the 2.5 line.** Upstream backports the #859 prefix
  support to a 2.4.x release. That 2.4.x release then becomes the target for a window that
  wants prefixes.

## Limits

The review covered the release page, the compare API's file list and patches, and two
upstream documents at the tag. The compare API returned no patch for 31 files, mostly
documentation, the `evals/` retrieval crate and `ai-memory-wiki/src/wiki.rs`. Their content
was not reviewed beyond the changelog entries. No 2.4.0 binary was downloaded or run on this
host.
