# ai-memory embedding compatibility — source review

Reviewed 2026-09-21. Read-only source inspection; no model calls, installs,
configuration changes, provider authentication checks or private corpus reads.
This is source compatibility evidence, not an inference benchmark or runtime E2E.

## Recommendation

Keep the current upstream local MiniLM provider for shared memory while the
separate SocratiCode model is qualified independently. MiniLM is a supported
compact baseline, not the latest state-of-the-art model. ai-memory 2.3.2 has no
configuration-only route that correctly gives an arbitrary asymmetric Hugging
Face retrieval model different document and query instructions. A newer symmetric
model that requires no task-specific preprocessing could use the supported
OpenAI-compatible endpoint, subject to separate serving, input-size, retrieval
quality and full re-embedding qualification. This review does not select or test
such a replacement.

An additional upstream issue was found: the Google provider implements separate
document/query semantics, but the MCP query call site currently bypasses the query
method. Therefore the Google implementation alone does not establish a clean
asymmetric retrieval path in this release.

## Source pin

- Repository: https://github.com/akitaonrails/ai-memory
- Installed release examined: `v2.3.2`
- Release commit: `353841d91618d20b110b208de284a74d0b960379`
- Current main also examined for the query call site:
  `1fe32bc2be32490ebf614c86eb9ab45718dcceb1`; the same call remains.

## Exact findings

1. **Supported providers and configuration.**
   [`config.rs` L1538–1554](https://github.com/akitaonrails/ai-memory/blob/353841d91618d20b110b208de284a74d0b960379/crates/ai-memory-cli/src/config.rs#L1538)
   accepts `openai`, `voyage`, `google`/`gemini`, `openai-compat`, `local`,
   `copilot`, and disabled aliases. There is no separate Ollama embedding
   provider. Ollama, LM Studio and vLLM use OpenAI compatibility.
   L332–338 expose provider/model/dimension/base URL fields; no query/document
   prefix or task-type configuration exists. L1563–1567 and L1615–1619 require
   explicit model and base URL for compatibility mode; dimensions must also be
   explicit. The compatibility key is optional (L1601–1609).

2. **The local model is fixed, not a general Hugging Face loader.**
   [`local.rs` L22–45](https://github.com/akitaonrails/ai-memory/blob/353841d91618d20b110b208de284a74d0b960379/crates/ai-memory-llm/src/local.rs#L22)
   pins `all-MiniLM-L6-v2`, 384 dimensions, a 512-token positional limit and the
   three model-file checksums. The tokenizer is configured with truncation.
   [`factory.rs` L257–261](https://github.com/akitaonrails/ai-memory/blob/353841d91618d20b110b208de284a74d0b960379/crates/ai-memory-llm/src/factory.rs#L257)
   constructs `LocalEmbedder::load(models_dir)` without forwarding a replacement
   configured model or dimension. Replacing the local model files is not a
   supported model selection method; checksum verification rejects drift.

3. **OpenAI compatibility cannot distinguish retrieval tasks.**
   [`embedding.rs` L52–59](https://github.com/akitaonrails/ai-memory/blob/353841d91618d20b110b208de284a74d0b960379/crates/ai-memory-llm/src/embedding.rs#L52)
   defines separate trait methods with identical default calls to `embed`.
   OpenAI compatibility overrides only `embed` (L324–347). Its shared request
   L188–211 contains only model/input, no task-type or instruction metadata.
   Therefore a server requiring different query/document prefixes cannot infer
   the correct role from this route. A single fixed server prompt would not
   resolve the missing distinction.

4. **Google's asymmetric implementation exists but its MCP call path is wrong.**
   [`google.rs` L62–84](https://github.com/akitaonrails/ai-memory/blob/353841d91618d20b110b208de284a74d0b960379/crates/ai-memory-llm/src/google.rs#L62)
   uses task types for Gemini embedding 001 and text prefixes for embedding 2.
   L179–184 provides document/query methods; L207–216 formats document text as
   `title: none | text: ...` and query text as
   `task: search result | query: ...`. However generic `embed` calls
   `embed_document` (L175–176), and
   [`server.rs` L1737–1742](https://github.com/akitaonrails/ai-memory/blob/353841d91618d20b110b208de284a74d0b960379/crates/ai-memory-mcp/src/server.rs#L1737)
   invokes `embedder.embed(query)` instead of `embedder.embed_query(query)`.
   Thus queries receive document treatment for that provider. This same call
   exists on the examined current main commit. The health wrapper itself
   forwards the query method correctly (`health.rs` L394–397); the MCP call site
   is the specific issue. No upstream issue or PR was created during this review.

5. **Page embedding is not chunked semantic RAG.**
   [`consolidate/embed.rs` L172–186](https://github.com/akitaonrails/ai-memory/blob/353841d91618d20b110b208de284a74d0b960379/crates/ai-memory-consolidate/src/embed.rs#L172)
   embeds a page body as one document; optional frontmatter abstracts are separate
   at L211–212. Compatibility mode applies nominal 5,000-token input budgeting,
   but
   [`text.rs` L36–40](https://github.com/akitaonrails/ai-memory/blob/353841d91618d20b110b208de284a74d0b960379/crates/ai-memory-llm/src/text.rs#L36)
   implements this through a hard maximum of **8,000 bytes**, not a model
   tokenizer. This does not guarantee fitting a 4,096-token model for arbitrary
   dense code. Google passes whole prepared text without this truncation.
   Changing models does not add document chunking or preserve tails lost through
   truncation. Scope/content lengths must be qualified against the actual model.

## Source SHA-256 values

| Release file | SHA-256 |
|---|---|
| `crates/ai-memory-cli/src/config.rs` | `7befb32d2ad1cf593546c7538bab87e624964eec5cf585caaaf4139d8280241a` |
| `crates/ai-memory-llm/src/embedding.rs` | `78c24d99b22d5c5e95f9b3c7cfda3645de381fdc6be1ad781b86ad60b5c487b2` |
| `crates/ai-memory-llm/src/local.rs` | `f4ec01f93b382c859e404618629d5f8f3de06c4ceab31b0d040674d9d0654a17` |
| `crates/ai-memory-llm/src/google.rs` | `0f824f98c439a939e49b22ce4b33fc27665b736bf92a3a79b6868c3cd9d470a3` |
| `crates/ai-memory-llm/src/factory.rs` | `4a422bf201abbafdfec4325aae0d00c95d3b0822692b50f0b2885906545fb012` |
| `crates/ai-memory-llm/src/text.rs` | `b3944ae1d5eecb4d6d24a749b648f70450f8ccfb890101291fe50c0454394a85` |
| `crates/ai-memory-consolidate/src/embed.rs` | `e7f5640b30740c8463422690cb16102da54a6248d3fc6d456960e9b436402d2a` |
| `crates/ai-memory-mcp/src/server.rs` | `b9cbe00cebae965a1769d0de3aab44cd9e7519527dbc2a90628bbf3fb76cfc1d` |

Current main `server.rs` SHA-256:
`84808694080977a018a77a928c06f2451db7367bd745d9d0dfd12fb6bb514a46`.

## Verification boundary

Source was fetched directly from the pinned upstream GitHub revision. Relevant
upstream provider tests were inspected as source references, not executed or
reported passed: `google.rs::v2_document_and_query_prefixes`,
`google.rs::embed_content_uses_api_key_header_not_bearer_auth`, and the existing
OpenAI compatibility integration tests. No private credentials or auth stores
were inspected. No hosted inference or new server was provisioned.
