# QMD lexical catalog instructions (2026-10-06)

The command center's local-model ruling assigns keyword search and document
retrieval to QMD and meaning-based catalog search to SocratiCode. The instruction
change must land before the configuration owner applies the QMD cutover. It
serves scoped retrieval for the native foundation that supports US-equities
research and simulation.

## Decision and sources

Carry this rule in the three named Claude token-lane blocks, the token-session
handbook, the Codex instruction template and its rendered copies:

> qmd for keyword search and document retrieval; codebase_search with the main checkout's projectPath for meaning-based search of the catalog; never run qmd embed or qmd pull.

The private command-center provenance is item
`task-ns2604-coop-20261006T224125Z`, section 2(a), and the ruling
`local-models-rulings-wf_96bbdf83-4f5.json`, `syn.apply[7].step`.
The ruling's SHA-256 is
`cc8dec6a8981966fdc6dfcb2929b6722843e30bd526c3b981e9289cdedd8059a`.
The item was verified against its coordination ledger digest; private host paths,
model stores and raw workflow output are omitted here.

- QMD [`v2.8.3`, `src/mcp/server.ts:294-296`](https://github.com/tobi/qmd/blob/v2.8.3/src/mcp/server.ts#L294-L296)
  supplies a lexical-only example. Its [typed searches and rerank controls at
  `:321-335`](https://github.com/tobi/qmd/blob/v2.8.3/src/mcp/server.ts#L321-L335)
  support explicit `lex` subqueries with `rerank: false`. The instruction uses
  those controls rather than the plain-text query's automatic expansion.
- QMD [`v2.8.3`, `src/mcp/server.ts:412-413`](https://github.com/tobi/qmd/blob/v2.8.3/src/mcp/server.ts#L412-L413)
  provides `get` line-window bounds. Named collections limit the search scope.
- SocratiCode [`v1.15.0`, `src/index.ts:138-146`](https://github.com/giancarloerra/SocratiCode/blob/v1.15.0/src/index.ts#L138-L146)
  provides semantic `codebase_search` with an optional absolute `projectPath`.
  This local rule makes that path explicit and selects the main checkout whose
  index the configuration owner maintains. [Markdown is a supported extension
  at `README.md:1325`](https://github.com/giancarloerra/SocratiCode/blob/v1.15.0/README.md#L1325).
- Repository [`f0d1c6d04`, `tools/adoption/managed_block.py:169-181`](../../tools/adoption/managed_block.py)
  is the existing Codex renderer; [`codex_roles.py:286-290`](../../tools/adoption/codex_roles.py)
  extracts the rendered F4 block. The seven RTK exceptions, role grants, model
  choices and effort remain those of the base.

The upstream tools support the retrieval interfaces. The catalog routing and
the prohibitions on embedding and model pulls are the user's local decision,
not a claimed upstream default. A role without a granted `codebase_search`
cannot gain that tool from instruction text; its coordinator supplies that
retrieval when needed. This PR changes no grants or server registrations.

## Alternatives and reopening

Keeping QMD's expanded semantic query, reranking or vector-index build is the
superseded route for this catalog. Keeping generic `qmd query` instructions
would leave that route available by default. The chosen instructions make the
lexical request explicit and retain SocratiCode's already indexed Markdown as
the meaning-based route. A later owner ruling backed by native read-back can
supersede this record in a new decision; historical decisions and receipts
remain unchanged.

The [new catalog-passage snapshot](../../evidence/artifacts/qmd-lexical-catalog-instructions-20261006/catalog-lookup-supersession.json)
links the active replacement to the original
`tests/fixtures/harness-context-moves/04.txt`. The original's 499 bytes, SHA-256
and frozen relocation contract are unchanged. The relocation test verifies
both the retained historical bytes and the replacement's presence in the
current handbook; its other passage cases retain their original assertions.

## Evidence boundary and host handoff

The [receipt](../../evidence/artifacts/qmd-lexical-catalog-instructions-20261006/receipt.json)
records source review, rendered-carrier consistency and local integration
checks. They establish repository consistency, not host cutover, native MCP
retrieval quality, organic use or token savings. No QMD command, model download,
index build, client write or gateway operation runs as part of this change.

After this PR and its base #803 land, the configuration owner applies the
ruling's cutover and re-renders installed instruction carriers in its window.
The owner then reads back the named lexical index and first-turn retrieval
through both clients. This lane applies nothing on the host.

## 2026-10-07 clarification: kept reranking and current maintenance

The J819 review identified two corrections to the current instruction carriers.
The original decided text above is retained as the dated source of this
clarification; its description of reranking as superseded is corrected here.
Lexical candidate retrieval does not imply a requirement to disable reranking.
The command-center ruling explicitly keeps BM25, query expansion and reranking
on the vector-less catalog index (`local-models-rulings-wf_96bbdf83-4f5.json`,
lines 22 and 34, SHA-256
`cc8dec6a8981966fdc6dfcb2929b6722843e30bd526c3b981e9289cdedd8059a`).

QMD [`v2.8.3`, `src/mcp/server.ts:334-335`](https://github.com/tobi/qmd/blob/v2.8.3/src/mcp/server.ts#L334-L335)
declares `rerank` optional and defaults it to true. A particular request may
choose `rerank: false`; this is an optional request choice, not a catalog-wide
policy. Typed lexical searches still select keyword candidates, and meaning-based
catalog retrieval still uses `codebase_search` with the main checkout's explicit
`projectPath`. The rule forbidding `qmd embed` and `qmd pull` remains unchanged.

The owner's cutover acceptance retains reranking: the ruling's lines 160 and
181 require a known-answer query with reranking on, returning its document
without a "Reranker unavailable" warning. A fresh session of each client must
read back the lexical index registration and answer that query after the owner
applies the cutover. This instruction PR neither runs nor claims that acceptance.

Both current `adoption/update.md` refresh workflows now wait for the owner's
applied and read-back `native-agent-stack-catalog-lex` cutover. They use that
index for later `update`, `status`, `search` and bounded `get`, and carry no
embedding or model-pull branch. QMD's embedding notice does not authorize those
operations. Its [bounded CLI syntax at `v2.8.3`, `README.md:1033-1037`](https://github.com/tobi/qmd/blob/v2.8.3/README.md#L1033-L1037)
is the source for the maintenance retrieval example.

The [new J819 followup receipt](../../evidence/artifacts/qmd-lexical-catalog-instructions-20261006/j819-followup-20261007.json)
links the prior receipts without rewriting them and retains the original
decision body's hash. The correction is to current instructions and this
explicitly requested dated addendum; historical receipts and frozen fixtures
remain unchanged. The lesson is to verify the complete ruling before treating
lexical candidate retrieval as a ban on its maintained reranker.
