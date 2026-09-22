# Repository quality and challenger review — September 21, 2026

This review keeps the accepted native foundation and expands the serious runtime
and memory comparisons. It does not declare an absolute winner, install every
candidate, or replace accepted pins with newer source revisions. Source capture
occurred on **September 22 UTC, still September 21 in America/New_York**.

The machine-readable [quality review](../catalogs/landscape/candidate-quality-review.json)
contains 16 pinned repository reviews and pointers covering all 20 existing
layers. Its [source snapshot](../evidence/artifacts/catalog-quality-review-20260921/sources.json)
records 58 immutable source files with SHA-256, public repository metadata and
observed release metadata. A release can concern a subpackage; it is not
automatically the version to install.

## What qualifies a candidate

Use six qualitative questions, with unknowns preserved:

1. **Task capability:** does the implementation address the actual task, account
   model and integration boundary?
2. **Evidence strength:** are relevant unchanged upstream tests/examples available,
   and what returned native outcomes and independent observations do we have?
3. **Maintenance and provenance:** can source, release and dependencies be
   identified and reproduced? Recency alone establishes no quality advantage.
4. **Licensing and deployment fit:** does the selected local/service/provider
   profile fit this deployment and its actual dependencies?
5. **Portability and lifecycle:** can the owned runtime install, restart, recover,
   restore scoped state and clean up on the intended machine?
6. **Measured cost:** what is the complete cost at matched answer quality,
   including retries, failed work, memory extraction, embeddings and hosting?

No numeric quality score is synthesized. Stars and awesome lists discover
candidates. README claims establish source-supported possibilities. Upstream test
source proves a test exists; it does not mean that test passed here. Review by
another harness is useful for finding omissions, not an independent oracle for
repository superiority. Follow the [acceptance evidence policy](acceptance-evidence-policy.md).

## Research runtime decisions

| Candidate | Source-supported strength | Current decision and missing comparison |
| --- | --- | --- |
| Native Codex/Claude, including the locked Codex research SDK | Existing account, tool and worker behavior has returned task evidence; the supported SDK environment already exists. | Retain the accepted foundation and [SDK recipe](../adoption/sdk/README.md). A default is not a benchmark win. |
| [DeerFlow](https://github.com/bytedance/deer-flow/blob/656db1223dda8883a09e7fde23f89da3a1a7a7dc/README.md) | Embedded Python, subagents, sandbox integration, native-provider/Claude integrations and a terminal interface provide a substantial existing harness. | Keep optional. Historical embedded ACP delegation completed; current full planning/UI hosting and recovery are unqualified. Preserve the tested adapter's read-only-label versus workspaceWrite/on-request finding. |
| [Deep Agents](https://github.com/langchain-ai/deepagents/blob/c9926b1a96d204309d0b211701b288ce3bb4244b/README.md) | Planning, filesystem backends, delegation and LangGraph persistence support an application-owned worker. | Add as a serious challenger, including its local-model routes. Require the same source-research task, permission boundaries, recovery and complete cost comparison. |
| [OpenHands SDK](https://github.com/OpenHands/software-agent-sdk/blob/9bc452ebf6b0093c531f25394c5ba5e9817ff910/README.md) | Agent Server, conversations/events and local or ephemeral workspaces support hosted workers. | Add as a remote/isolated-worker challenger; installation and native-account/recovery acceptance remain open. |
| [OpenHands Agent Canvas](https://github.com/OpenHands/OpenHands/blob/2f8539de2fafbde5226c7e41c0d0aa7bea2533fa/README.md) | Current control center can host native Claude/Codex and other ACP agents across backends. | Correct the outdated replacement-agent-only framing. Hosting existing workers may be useful; it is not yet qualified here. |
| [Microsoft Agent Framework](https://github.com/microsoft/agent-framework/blob/98a982a147212424d766ed993e6ecda13abe5faf/README.md) | Python/.NET agent applications, providers, graph workflows and checkpoints broaden the comparison. | Fill a discovery gap; qualify a required application workflow before adding another runtime. |

The [foundation worker layer](../catalogs/landscape/foundation.json) and
[domain operations layer](../catalogs/landscape/us-equities.json) also retain
LangGraph, the official application SDKs, Dagu/systemd, Temporal, Restate,
Prefect and Dagster in their respective scopes. Those existing source reviews
are preserved, not presented as freshly rerun tests.

The old [DeerFlow research receipt](../blueprints/us-equities/deerflow/research-receipt.json)
and [native receipt](../blueprints/us-equities/deerflow/native-receipt.json)
remain historical evidence. This source refresh did not invoke DeerFlow or any
model. A separate runtime-review receipt must identify any fresh execution.

## Memory decisions and corrected exclusions

| Candidate | Actual reason to compare | Current decision |
| --- | --- | --- |
| [ai-memory](https://github.com/akitaonrails/ai-memory/blob/5157c6be10b5830d7adc7e29b0a4358c3ecbe6a2/README.md) | Cross-client project continuity with historical native capture, retrieval, maintenance and restoration. | Retain one authoritative project store; keep comparative recall, useful learning and complete cost open. The reviewed upstream revision is not a new installed/accepted pin. |
| [Hindsight](https://github.com/vectorize-io/hindsight/blob/680406b3dd9cca2108c7f0e204820a09b4e30906/README.md) | Retain/recall/reflect, temporal or experiential memory, local providers and documented native Codex/Claude subscription providers. | Priority challenger. API-key-only or cloud-only exclusion is stale; published benchmark claims require a matched workload. |
| [Basic Memory](https://github.com/basicmachines-co/basic-memory/blob/3bf2d523c0a941f71cb144a5502e7557dd025d69/README.md) | Editable Markdown and MCP, plus Claude session briefings, pre-compaction checkpoints and opt-in capture. | Priority challenger. It is not merely manual notes. Qualify actual capture, isolation, restore and AGPL deployment fit. |
| [Mem0](https://github.com/mem0ai/mem0/blob/a39a802bbc93e85b820078cd3c4dbaf53af25dbe/README.md) | User/session/agent memory and time-aware retrieval, with published evaluation references. | Conditional application-memory or project-recall comparison; no local superiority trial. |
| [Graphiti](https://github.com/getzep/graphiti/blob/16cdf7045378c8d53ae01f94e2fa60d238cb0f68/README.md) | Temporal relationships among entities and sourced observations. | Conditional research graph; cannot invent historical source availability or replace deterministic execution state. |
| [Claude-mem](https://github.com/thedotmack/claude-mem/blob/4520de9e0f8d6cdc20597520e383d8b51d93137f/README.md) | Capture, compression and retrieval, with documented integrations beyond Claude including OpenCode. | Compare scoped capture and provider behavior. Do not dismiss as Claude-only or run overlapping stores by default. |
| [Letta Code](https://github.com/letta-ai/letta-code/blob/dfb5639a4db2d97828e7ca07b808e93be85e05e7/README.md) | Stateful harness with memory/skills and local/cloud backends. | A broader runtime comparison, not just a store swap. [Legacy Letta](https://github.com/letta-ai/letta/blob/5bcdd177d70fa2b31a754cfcd801e77b2e1ab16a/README.md) points to current Letta Code; retired V1 is on an archive branch, while the repository itself is not archived. |
| [Cognee](https://github.com/topoteretes/cognee/blob/663a2dc15d04bc0d7ec2733a2dd604b7ed1b8c8e/README.md) | Graph/context assembly from documents, code and conversations, with local extraction/embeddings available without cloud keys. | Conditional research-corpus candidate. Its default LLM example still uses OpenAI; qualify the chosen profile. |
| [OpenViking](https://github.com/volcengine/OpenViking/blob/172c1050716f63339f4001292d58c830e6b7a315/README.md) | Hierarchical resource/memory/skill context, scoped retrieval and inspectable session-derived Markdown. | Conditional unification candidate; benchmark transfer, migration and AGPL deployment fit remain open. |
| [Supermemory](https://github.com/supermemoryai/supermemory/blob/57b430b5b6a19106a989651f4cde853c05147682/README.md) | Application memory/search/profile APIs with a local server, local embeddings and an Ollama route. | Cloud-only exclusion is stale. Qualify actual provider calls, export/restore and isolation before adoption. |

The [memory lifecycle evidence](native-memory-rag-lifecycle.md) supports current
ai-memory integration. It does not prove better subsequent answers than these
alternatives. Use the same held-out questions, source citations, stale-fact
handling, abstention, project isolation and restored state for any comparison.
Measure complete operation cost only when the provider and infrastructure
observations are available.

## Coverage and continuation

Before this refresh, **188 candidate-layer rows represented 150 distinct
case-insensitive repository identities**. The revised comparison layers contain
**207 rows and 157 identities**. Repeated repositories serve different layers;
they are not additional independent evaluations.

The broader discovery inventory now contains 527 identities after registration
of these reviews. Public stars and historical cards have different scopes.
This document does not claim all discovered repositories
or every awesome-list link received a current source or runtime evaluation.

All 20 layer requirements, present choices, evidence gaps, named challengers and
overturn conditions remain in the two layer catalogs and are cross-referenced in
the quality review. Valid source and native evidence was not discarded merely
to repeat it in a fresh review.

For a new WSL machine, reproduce a selected owned profile and useful task using
the [adoption guide](../adoption/README.md); establish that machine's own sign-in,
scope, install and recovery observations. Current-source installability,
historical task acceptance and clean-WSL acceptance are distinct. GPU services,
container hosts, external providers and memory migrations need their matching
qualification before being marked ready.

## Verification of this source-review update

Scoped structural checks passed: all 20 layers retain requirements, choices,
evidence gaps, challengers and overturn conditions; all 207 candidate-layer rows
have valid unique per-layer identities and existing local evidence references.
All 16 quality-review candidates are explicitly labelled source review, including
ai-memory and DeerFlow: their older native receipts do not qualify these new pins.
The 58 immutable source files were independently refetched; all SHA-256 and byte
counts matched. These checks establish artifact consistency, not behavior.

The required publication validator was run before handoff and reported the two
changed layer-file hashes/byte counts and the new unlisted source artifact.
The landscape validator reported the new OpenHands SDK identity absent from the
old canonical index. The coordinator must register/regenerate the index, hash
inventory and HTML, then run the full validators and independent review before
integration is complete. This worker did not modify those coordinator-owned files.
