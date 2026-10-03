# Historical native runtime evidence port, 2026-10-03

historical; sets no default; runtime-job selection is owned by the runtime-jobs lane (#633)

This record preserves #566's dated native capability evidence for the foundation
workers that will build and review the north-star research systems. It qualifies
only the recorded tasks, inputs and host. The port performs artifact checks;
it runs no provider/model calls, installs or historical trials.

## Provenance and byte preservation

- Source: [PR #566](https://github.com/seathatflowsinourveins/native-agent-stack/pull/566),
  head `e9bd476cdab11751ee7be00ac2c954ce65ff3c60`.
- Source merge base: `46365ea812c3a680b19c8c8c9c3bb198bf3b38ab`.
- Frozen trial base: `29458b4342422c979ad3b9bc62532ea6f05073c1`.
- Content build base (before rebase): `cac8700ba914950266272347468bff7ad630a4bf`.
  The content commit was then rebased onto main
  `1f5a791b02a230aced670c88bab3d3d0ebcf401a`, the PR's base at publication.
- The source branch is left unrewritten. The 13 original artifacts, receipt and
  16 example files are carried at their original paths. The receipt and
  convergence record receive only the two rebindings below; all other carried
  bytes, failed attempts, negative controls, usage scopes, executed-source
  archives and anti-patterns remain unchanged.
- The old live-guidance document
  `docs/native-runtime-role-resolution-20260930.md` is omitted. Nothing is added
  under `catalogs/foundation/`. Its dated role table is preserved below.

## Moves and rebindings

| Item | Original | Port |
| --- | --- | --- |
| Role packet path | `catalogs/foundation/native-runtime-role-resolution-20260930.json` | `evidence/artifacts/native-runtime-role-resolution-20260930/role-packet-20260930.json` |
| Role packet bytes | 18,535 bytes; SHA-256 `d8c9922b0e85feba8002dd8df51db0d38eae895b9072bb8d8007ae8df0176a63` | Identical bytes and hash |
| Receipt `data.source_packet` | Original packet path | Relocated packet path; the only receipt content edit |
| Receipt SHA-256 | `f5ed23084343adf453c10532b5196637139d80f030247b4145e8750e8b11ec96` | `09ca4ef4a20e2c2f966838f0a6ffe89856e03bd06e5c48447c44b8125e459ac2` |
| `experiment.json` receipt binding | Original receipt SHA-256 at source line 729 | Port receipt SHA-256; the only convergence-record content edit |

`completeness-critic.json` remains the critic's byte-identical returned output.
Its source line 39 still names
`catalogs/foundation/native-runtime-role-resolution-20260930.json`, a pre-port
pointer whose carried bytes now reside at the relocated path above. The packet's
dated declarations and any other historical pointers remain historical.

## Dated role table from the omitted 2026-09-30 document

These rows describe that document's historical positions, not current dispatch
instructions or measured winners. The original table is available in the
[immutable source document](https://github.com/seathatflowsinourveins/native-agent-stack/blob/e9bd476cdab11751ee7be00ac2c954ce65ff3c60/docs/native-runtime-role-resolution-20260930.md).

| Task | 2026-09-30 position | Historical acceptance and limits |
| --- | --- | --- |
| General engineering and structured coding workers | Retain Codex SDK 0.159.2, Sol-Max worker and Astra-Max consequential judge through OmniRoute; native parents retain their accounts | **Stale row.** It cited #551 as a draft. The custody snapshot recorded #551 closed and #628 open; the read-only refresh below records #628's subsequent merge. Current runtime-job selection belongs to #633. |
| Terminal/headless/ACP OpenHands interface | CLI 1.16.0 installed on Python 3.12; strict cache isolation held | 108 unchanged upstream tests passed; cache isolation remained held. |
| OpenHands LLM, skills/plugins, MCP and condenser | SDK/tools 1.50.1 with LiteLLM 1.93.2; native configuration and one LLM round trip passed | 184 unchanged upstream tests passed. Production MCP, full agent conversation and condenser execution remained separate. |
| Multi-step research with explicit specialist context and persisted continuation | DeepAgents 0.7.21 locally qualified for the bounded source-research and fresh-process continuation task | The original 24-step attempt failed; one saved-context 32-step repair passed. |
| Manifest/skills/shell/filesystem sandbox harness | OpenAI Agents SDK 0.22.3 beta SandboxAgent as a supported alternate | Source review only; provider and isolation required a future same-role trial. |
| Typed extraction or application judgments | Pydantic AI conditional trial | The source packet's typed-decisions row; no new native acceptance here. |
| Explicit graph state or durable application execution | LangGraph conditional; Temporal only for an execution-replay requirement | Dagu's scoped acceptance was retained; checkpointed conversation state and execution replay had separate contracts. |
| Extensible terminal/server/editor interface | Coordinate Pi's owner; OpenCode, Goose and Cline conditional | Interface pins and source boundaries remained those in the dated packet. |
| Product framework or served agent platform | Mastra conditional; Agno/Microsoft/other deployments subject to a demonstrated product requirement | Catalog inclusion started no service. |
| Independent agent/task evaluation | Executable task oracle retained; Inspect/Inspect SWE or Harbor as evaluator candidates | A common frozen task envelope was required before a framework comparison. |

**Dated correction, verified 2026-10-03:** [#551](https://github.com/seathatflowsinourveins/native-agent-stack/pull/551)
closed at `2026-10-03T03:43:42Z`. The custody contract's earlier snapshot described
[#628](https://github.com/seathatflowsinourveins/native-agent-stack/pull/628) as
open; a builder read-only `gh pr view 628 --json state,mergedAt,mergeCommit`
returned `MERGED`, `2026-10-03T16:11:37Z`, merge commit
`ecea28654a835fff2cc3651bab77ca0e46b9bec5`. The stale coding row is preserved as
a dated fact and supplies no current version or default claim.

## Retained evidence classes and counts

| Recorded result | Evidence class and scope |
| --- | --- |
| OpenHands CLI: 108 passed; standalone SDK: 184 passed | Historical unchanged upstream tests at their pinned revisions. Earlier SDK scope/naming failures remain retained. |
| DeepAgents: 361 passed plus 1 expected failure | Historical unchanged upstream tests in the separate upstream-lock environment. |
| One OpenHands OmniRoute Sol-Max round trip: HTTP 200, 85 total tokens (36 input; 49 output, 34 of them reasoning; `openhands-llm.json` `provider_usage`) | Historical native execution of the bounded LLM operation; no comparative framework or full-conversation claim. |
| DeepAgents original 24-step attempt failed; one 32-step saved-context repair passed; fresh-process SQLite continuation passed | Historical native execution with a locally authored task/oracle; original and repaired conditions remain distinct. |
| 28 scoped requests; 27 unique AI-message usage records | Historical scoped wire observation and independently deduplicated returned usage. Complete provider billing/backend identity and whole-task savings remain unknown; subset counters are not summed twice. |
| Port hashes, pointers and registration | Structural/local integration checks of the carried bytes; no new runtime or model execution. |

The authored oracle is **synthetic/local_integration**. It is not the
preregistered upstream-evaluator comparison required by the runtime-jobs method.
The original observations do not establish a universal winner, OS confinement,
arbitrary interrupted-tool replay, full provider accounting or runtime defaults.

## Held conditions and review state

- The CLI's pinned SDK 1.21 Jinja cache hard-codes the home directory. Strict
  cache isolation remains held; CLI persistence settings do not resolve it.
- The standalone SDK's `OH_PERSISTENCE_DIR` must be set before import. The
  original failed configurations and subsequent scoped repair remain retained.
- CodeQL alert #81's #566-head instance was fixed through native LangChain
  Core 1.6.6 secret-aware serialization. The published worker SHA-256 remains
  `cc6ebc1878b4b10f295e59a18cde7afc152a6dd7bd4faf6e7f5eb64ef2ede8cd`;
  archived executed sources and the post-trial distinction remain unchanged.
- The historical native Claude Opus/max peer call exited 124 after 180 seconds
  with no verdict. No new review or runtime-jobs acknowledgement is claimed.
- The port still needs the runtime-jobs lane's explicit ack, an independent
  Opus/max review of its exact head and current required GitHub checks before
  publication custody can close #566. Silence is not acknowledgement.

## Pinned upstream sources

These are the historical revisions the port preserves, not updates installed by
this run. Exact source locators and supported commands remain in the unchanged
packet, installation artifacts and example recipes.

| Component | Pin | Upstream source locator |
| --- | --- | --- |
| OpenHands CLI | 1.16.0 @`2963442dacc7cea44e39b7c4e73724295c853465` | [OpenHands/OpenHands-CLI](https://github.com/OpenHands/OpenHands-CLI/tree/2963442dacc7cea44e39b7c4e73724295c853465), native CLI and selected upstream tests named in `openhands-install.json` |
| OpenHands SDK/tools | 1.50.1 @`1e1390acc8788346ba4804c34323284009bf3f5e` | [OpenHands/software-agent-sdk](https://github.com/OpenHands/software-agent-sdk/blob/1e1390acc8788346ba4804c34323284009bf3f5e/openhands-sdk/openhands/sdk/llm/llm.py), `LLM.generate` and native SDK tests |
| LiteLLM | 1.93.2 @`cd1bd0f4b8af865f8d05fbd938392fdd4703babc` | [BerriAI/litellm](https://github.com/BerriAI/litellm/blob/cd1bd0f4b8af865f8d05fbd938392fdd4703babc/litellm/litellm_core_utils/get_llm_provider_logic.py), provider-prefix resolver |
| DeepAgents | 0.7.21 @`4394bcd00b8eb46e7c423939643a0dfcfb5d8773` | [langchain-ai/deepagents](https://github.com/langchain-ai/deepagents/blob/4394bcd00b8eb46e7c423939643a0dfcfb5d8773/libs/deepagents/deepagents/graph.py), `create_deep_agent` and selected unchanged unit tests |
| LangGraph checkpoint-sqlite | 3.1.1 @`b2926a0ff9589c28c7e01fe7cdbb337b86d5a4b4` | [langchain-ai/langgraph](https://github.com/langchain-ai/langgraph/tree/b2926a0ff9589c28c7e01fe7cdbb337b86d5a4b4/libs/checkpoint-sqlite), matched released SQLite checkpointer source |
| LangChain Core | 1.6.6 @`04ac76c07ec173a44e3e57de54861d0b637e3299` | [langchain-ai/langchain](https://github.com/langchain-ai/langchain/blob/04ac76c07ec173a44e3e57de54861d0b637e3299/libs/core/langchain_core/load/dump.py), native secret-aware `dumps` |
| OpenAI Agents SDK | 0.22.3 @`fdf21db62c303a3db54b0dfbee82de2141fa2799` | [openai/openai-agents-python](https://github.com/openai/openai-agents-python/tree/fdf21db62c303a3db54b0dfbee82de2141fa2799), SandboxAgent alternate reviewed in the unchanged role packet |

## Custody decision and completeness boundary

The assigned disposition is port-and-close after the new publication's gates.
Absorbing the evidence into #633 or retiring it are coordinator alternatives if
the runtime-jobs lane requests them. A carried-lock security finding, secret-scan
finding or required change to substantive receipt claims is a stop condition;
pins and historical evidence are not rewritten to obtain a pass.

The unchanged completeness critic covers runtime roles, skills lifecycle,
MCP/automation, modalities/platforms, evaluation/usage and owner review. Its
missing browser/computer-use, multimodal, GPU/remote, cross-platform, production
MCP and common-evaluator acceptance remain missing. The next scoped runtime-jobs
sweep must use its frozen upstream-evaluator method; the next skills sweep stays
keyed by discovery, verification, installation, activation, upgrade, rollback
and recovery. This custody port supplies no new landscape or adoption claim.
