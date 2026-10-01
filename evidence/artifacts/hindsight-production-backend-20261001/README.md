# Hindsight backend qualification, 2026-10-01

The isolated local Hindsight 0.10.2 backend passed actual extraction,
consolidation, corrected recall, reflect, derived-page, project-bank isolation,
source deletion, independent local transfer and full native API/database recovery.
All synthetic backend-test banks were deleted before handoff. A later fresh
Claude capture and fresh-session recall also passed, as recorded in the separate
[client capture receipt](client-capture-receipt.json). Its later native scheduled
Conventions page also completed with independently observed content. Automatic
cold-start seed, the remaining pages and the original checkout's memory cutover
remain separate gates.

The [receipt](receipt.json) distinguishes unchanged upstream tests, our native API
integration checks, synthetic inputs and independent observations. Returned API
responses, logs, the test reports and the transfer archive remain in private owned
state; the receipt records hashes. There is no locally authored E2E runner.

## Sources and supported commands

- [Hindsight v0.10.2 release](https://github.com/vectorize-io/hindsight/releases/tag/v0.10.2)
  and its [native API source](https://github.com/vectorize-io/hindsight/blob/v0.10.2/hindsight-api-slim/hindsight_api/api/http.py)
  define the exercised endpoints and request models. The input JSON in
  [fixtures](fixtures/) was constructed for this synthetic integration check.
- [Coding-agent integration 0.8.0 source](https://github.com/vectorize-io/hindsight/tree/f9d9e2ab88bd237a81bba12f0ac5cf173aafd46c/hindsight-integrations/coding-agents)
  is pinned to its npm gitHead. The installed runtime matched every overlapping
  file from the published package. The unchanged upstream command was
  `npm ci`, then `npm test -- --reporter=json --outputFile=<private-report.json>`.
  The archive's missing git metadata caused the first test failure; after fetching
  the pinned commit and restoring the index, the unchanged suite passed 1,279
  tests with six pending Trae SQLite cases. This is not the server's full suite.
- [Hindsight's builtin Pg0 integration](https://github.com/vectorize-io/hindsight/blob/v0.10.2/hindsight-api-slim/hindsight_api/pg0.py)
  supports `pg0://<named-instance>:<port>` and calls Pg0 start when needed.
  [Pg0 v0.15.2](https://github.com/vectorize-io/pg0/tree/v0.15.2) supplies that runtime.
  Final qualification uses the native builtin database rather than an externally
  started database requiring a separate startup command.

Native tool installation, using isolated `UV_TOOL_DIR` and `UV_TOOL_BIN_DIR`, was
`uv tool install hindsight-embed==0.10.2` and
`uv tool install hindsight-api==0.10.2`. Installed 0.10.2 help supplies the supported
profile lifecycle; its `configure` command is deprecated:

```text
hindsight-embed profile create <owned-profile> --port <free-loopback-port> --env <supported-key=value> ...
hindsight-embed profile set-env <owned-profile> HINDSIGHT_EMBED_API_DATABASE_URL pg0://<owned-instance>:<free-database-port>
hindsight-embed -p <owned-profile> daemon start
hindsight-embed -p <owned-profile> daemon status
hindsight-embed -p <owned-profile> daemon stop
```

The owned API was bound to loopback. It preserved the existing local
OpenAI-compatible model route; embeddings and reranking used local CPU models.
No sign-in, authentication store or existing credential value was read/copied.
Native stop closed both the API and builtin PostgreSQL listener and removed both
PIDs. One native start recovered both and preserved two corrected records and the
521-character derived page. This establishes recovery, not boot-service adoption.

Native HTTP operations used `curl --data-binary @fixtures/<file>.json` for bank
creation, retain, recall, reflect and page creation, followed by native operation
polling. Export used `POST /banks/<source>/transfer/export?include_bank_config=false`.
Import used `POST /banks/<existing-control>/transfer/import?target_bank_id=<absent-target>&include_bank_config=false`
and native multipart `--form file=@<private-transfer.zip>`. The URL control bank
must exist so the API can record the operation; the target must be absent.
The independent restore used another backend/database with LLM provider `none`,
preserved facts, observations and the page, and made no re-extraction call. It was
a separate instance on the same host, not a second-host restore.

## Client and capture boundary

The supported installer is
`npx @vectorize-io/hindsight-coding-agents@0.8.0 install codex claude-code --server self-hosted --api-url <qualified-loopback-api>`.
[Installer source](https://github.com/vectorize-io/hindsight/blob/f9d9e2ab88bd237a81bba12f0ac5cf173aafd46c/hindsight-integrations/coding-agents/src/installer.ts)
merges the three native hooks, installs the companion skill and registers MCP.
It preserves existing behavioral configuration, including `disabled: true`.
`install --help` does not implement a help-only flow.

The single supported config is `~/.hindsight/coding-agent.json`, or the path in
`HINDSIGHT_CONFIG`. [Bank resolution source](https://github.com/vectorize-io/hindsight/blob/f9d9e2ab88bd237a81bba12f0ac5cf173aafd46c/hindsight-integrations/coding-agents/src/core/bank.ts)
supports explicit unique `mapPathToBank` entries, `optInOnly: true` and worktree
resolution. Initially approve only production/qualification checkout paths;
approving the main root also approves its worktrees. Future approved repositories
need their own unique bank mapping.

The incumbent [ai-memory v2.4.2 native capture gate](https://github.com/akitaonrails/ai-memory/blob/v2.4.2/crates/ai-memory-cli/src/commands/hook.rs#L568-L603)
already uses allowlist mode on this host. Both harnesses' unchanged native
`hook --check-capture` commands proved that the original marker-bearing checkout
is admitted, while the owned marker-free production and Codex qualification
checkouts are excluded before spool/network activity. No marker was removed and
no global capture policy changed. `[capture] ignore_paths` filters tool capture;
it cannot be described as a full lifecycle opt-out.

No approved historical user memory was manually imported by this worker. The
coordinator's later automatic configuration enables the upstream seed/survey
flow. Its initial 300-commit git seed timed out. The subsequent 20-commit
attempt also failed. Its requested 300-second timeout used an ineffective
`HINDSIGHT_EMBED_API_LLM_TIMEOUT` key; the stored global API timeout remained 90,
and the historical effective request deadline was not directly measured. Both
failed attempts retain unknown provider usage. The coordinator escalated the unresolved
cold seed to Astra/Max. The stored Conventions cron queued an actual refresh at
03:57 UTC and completed at 03:59 UTC with 5,045 characters, `content_written` and
`is_stale: false`. Its stored response exposes no per-refresh provider usage.
The remaining four pages are not requalified by that result. These gates remain
separate from the passed session capture and retrieval. Root owns
the serialized client activation, trust review, cross-client checks,
original-checkout ownership coordination and any production service adoption.
