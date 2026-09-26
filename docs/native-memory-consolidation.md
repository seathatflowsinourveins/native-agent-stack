# Native cross-harness memory consolidation

The later [memory landscape and maintenance qualification](memory-landscape-maintenance.md)
enables native learning and bounded assistant capture. The setup below records
the earlier consolidation wave; its disabled learning-scheduler statement is
historical, not the current default.

The 2026-09-21 gap-resolution run qualified ai-memory 2.3.2's native Codex
provider against the existing native account. A real completed Claude session
was compiled by Codex, persisted as a session page, retrieved through MCP and
inspected in the official read-only wiki. This closes the disabled-consolidation
gap in the [earlier rendered review](dashboard-rendered-acceptance.md).

**Update 2026-09-26, GPT-6 models.** The `gpt-5.6-luna` configuration below is
historical. With `llm_provider = "codex"`, ai-memory 2.3.2 and 2.4.0 send
`temperature`, and gpt-6-luna, gpt-6-sol and gpt-6-astra reject it with
`400 {"detail":"Unsupported parameter: temperature"}`. That was observed with a
2.3.2 build on the WSL authoring laptop on 2026-09-26 (UTC). 2.4.0 ships the same
three request files unchanged.
Upstream [#852](https://github.com/akitaonrails/ai-memory/pull/852) (merge
`f7ec2eda`, issue [#851](https://github.com/akitaonrails/ai-memory/issues/851))
omits it for `gpt-6*`. The fix is in
[v2.4.1](https://github.com/akitaonrails/ai-memory/releases/tag/v2.4.1) and
`release/2.5` (at `dde5806b` on 2026-09-26), but not in 2.3.2 or 2.4.0.

A host on 2.4.1 can set a GPT-6 model directly. The laptop stays on 2.3.2 for
its [#859](https://github.com/akitaonrails/ai-memory/pull/859) prefix backport,
so it runs a local 2.3.2 build carrying both backports. Its three changed Rust
files are byte-identical to `f7ec2eda`, and it has run `llm_model = "gpt-6-sol"`
at medium effort since 2026-09-26 (UTC). That model choice is keep-but-compare:
a restored-store evaluation of two sessions cannot separate sol from astra or
luna. A larger comparison with repeated runs, blind page-quality review and
per-call usage would settle it.

## Upstream setup and returned results

Use the host's existing native Codex home and executable; do not copy its
authentication store into the repository or another client profile.

```sh
codex login status
ai-memory backup --to /private/backup/before-provider.tar.gz
ai-memory llm-test --provider codex --model gpt-5.6-luna --prompt 'Reply with OK'
ai-memory llm-test --provider codex --model gpt-5.6-luna --structured --prompt 'Return a short answer'
ai-memory status
```

The native plain check returned:

```text
--- model: gpt-5.6-luna ---
--- usage: in=9 out=5 ---
OK
```

The structured check returned `{"answer":"How can I help?"}`. Its CLI path
does not print usage. The numbers above describe only the plain provider probe;
they are neither lifetime usage nor saved tokens.

Supported configuration uses `llm_provider = "codex"`,
`llm_model = "gpt-5.6-luna"` and `llm_reasoning_effort = "medium"`.
The service receives `CODEX_HOME` and `AI_MEMORY_CODEX_EXECUTABLE` for the
native profile. Local MiniLM embeddings, repository capture allowlisting,
disabled historical backfill and disabled auto-improvement scheduler were
preserved. Service restart was necessary to load provider configuration.
The first immediate status check encountered startup connection refusal; the
subsequent check passed without another configuration change.

Enabling the provider also enables upstream PreCompact checkpoints. The
separate `consolidate_on_session_end = true` flag enables native processing of
future eligible completed sessions. Before activation, read-only inspection of
the native `session_consolidation_jobs` table returned no jobs, so there was no
pending historical backlog to start. The all-project auto-improvement scheduler
remains disabled; it is a different capability.

## Actual session operation

The upstream `memory_consolidate` tool received an explicitly selected completed
Claude session ID. `dry_run: true` confirmed the admitted target path without
calling the model; it is not a preview of generated prose. The subsequent
`dry_run: false, multi_page: false` call returned a nonempty page ID, title,
body and tags. MCP readback retained `agent: claude-code`, `consolidated: true`
and the original session as its source. Provider health then reported Codex
and local embeddings both `ok`.

The generated page faithfully records that session's historical status check,
including the then-disabled provider. It is a dated observation, not a current
configuration page. The official wiki page was opened and its full screenshot
inspected; API persistence and rendered content agree.

After enabling session-end processing, a second normal native Claude status
task completed and emitted all five lifecycle observations. Read-only inspection
of the native queue recorded generation 5, `completed`, attempt 1 and no error.
MCP readback returned the automatically compiled page with Claude attribution
and `consolidated: true`. No manual consolidation call was made for this second
session. Its immediate post-restart status correctly recorded provider health
as `unknown`; subsequent native status after processing reported both providers
`ok`. Health history resets when the service restarts.

A fresh native `codex exec --json` status task also completed. Its ten native
observations included SessionEnd; the persisted generation-10 job completed on
attempt 1 without error. Readback retained the Codex source attribution. This
separately qualifies the native Codex client end-hook path. The installed
Desktop session is still active; its eventual SessionEnd and a fresh PreCompact
event were not forced by this test.

Native client accounting for these two automatic-path checks is consumption:
Claude returned input 34, cache creation 12,115, cache read 21,205 and output 773;
Codex returned input 122,500, cached input 99,072, cache write 0, output 4,333 and
reasoning output 3,935. Cached input is a subset of input, and reasoning output
is a subset of output; do not add the subset fields. These client totals do not
include ai-memory's separate model calls, whose consolidation response does not
return usage. No complete-task or lifetime savings are inferred.

The successful native Codex run retained Linux keyring warnings because no
Secret Service was running. The supported native setting
`mcp_oauth_credentials_store = "file"` avoids that unavailable backend without
changing the separate client login store or copying credentials. The model-free
`codex mcp list --json` check returned all five configured local MCP entries
with no stderr using this setting. Their `unsupported` OAuth statuses mean
these local servers do not offer OAuth; they are not authentication failures.
This is a Linux native profile correction; Desktop settings remain separate.
See the [official configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference)
and [installed-source store resolution](https://github.com/openai/codex/blob/be2951ea34f0d295ed0becf97079f92fa5f6950e/codex-rs/rmcp-client/src/oauth/resolved_store.rs#L190).

The stale pinned deployment decision was superseded using the upstream ADR
pattern: a new accepted decision describes the qualified configuration, and
only the original decision's Status line changed. Its historical substance
remains intact. The current decision's complete rendered screenshot was inspected.

The wiki remains read-only by design, and browser search is global FTS. Use
explicit workspace/project scope for CLI/MCP retrieval. A compiled status
session is bounded functional evidence, not broad summary-quality evaluation or
proof of token savings. Raw session content, backup and authentication remain
private; public receipts bind retained evidence by hashes.

## Source contract

Reviewed upstream release: `353841d91618d20b110b208de284a74d0b960379`.
The [native provider guide](https://github.com/akitaonrails/ai-memory/blob/353841d91618d20b110b208de284a74d0b960379/docs/llm-providers.md)
documents CLI-owned Codex authentication and the provider test command.
The [consolidation implementation](https://github.com/akitaonrails/ai-memory/tree/353841d91618d20b110b208de284a74d0b960379/crates/ai-memory-consolidate)
owns the source-derived page and evidence write. Upstream source review, native
provider execution and local configuration integration are separate evidence.
