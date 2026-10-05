# Clean WSL memory runtime qualification

The [runtime manifest](manifest.json) fixes this execution wave's candidate list:
ai-memory as the native operational reference, Hindsight as the shared lifecycle
and conversational-quality challenger, and agentmemory as the local retrieval
challenger. MemPalace remains a reserve; Mem0 requires a separately selected
managed profile. A best-backbone or token-efficiency winner remains unestablished.

Use the existing `foundation-cpu` profile and Linux/WSL2 recipe in
[adoption/manifest.json](../../../adoption/manifest.json) and
[adoption/bootstrap.md](../../../adoption/bootstrap.md). This qualification
installs into a new owned prefix on the current host, leaves active client wiring
and production memory intact, and retains native sign-ins. It does not create
a new WSL distro or establish second-machine acceptance.

The supported bootstrap installs pinned artifacts and probes versions. It may
retain the existing auto-updated Claude native launcher above its minimum pin.
That is an explicit dependency on the current host, not a fully independent
client installation. A separate distro should start from the attested catalog
release and complete native sign-in, configuration and lifecycle acceptance.
The bootstrap also retains the existing npm cache. Current reviewed pins have
Codex 0.159.2 and Claude 2.1.284 as a minimum; the published September 26 release
has older client pins. This execution is explicitly current-checkout staging,
with its inputs frozen before installation, rather than release acceptance.

For an eventual separate distro, use the official [Codex WSL guidance](https://developers.openai.com/codex/windows/wsl/)
and [CLI installation/sign-in instructions](https://developers.openai.com/codex/cli/):
keep repositories under the Linux home filesystem and complete each native
client's sign-in. The existing adoption platform page supplies the broader
stack recipe. No active host configuration or credential store is an export
template for that distro.

The execution wave reuses maintained sources: agentmemory's pinned upstream
`eval:coding-life` harness and sandbox, ai-memory's supported lifecycle commands
and the repository's unchanged lifecycle fixture, and Hindsight's previously
recorded pinned package qualification. Actual logs and failed attempts stay in
owned private locations; sanitized receipts bind their hashes and distinguish
upstream tests, integration fixtures, published benchmarks and live acceptance.

The [evidence review](../../../docs/memory-rag-foundation-20260930.md) and
[backbone assurance record](../../../evidence/artifacts/memory-rag-20260930/backbone-assurance.json)
define what the evidence supports. The existing replacement rules remain
binding. Passing installation or a small retrieval fixture is useful evidence,
but does not select the production backbone.

| Execution | Observed result | Acceptance boundary |
| --- | --- | --- |
| Foundation profile | Supported bootstrap exit 0; ten verified probes, zero failures. | Installation on the current host; existing Claude launcher and npm cache retained. |
| ai-memory 2.4.2 | 101 lifecycle-fixture checks and 65 recovery-fixture checks pass; 42 unchanged upstream scope tests pass. | Synthetic native store integration and backup/empty-target restore. Initial process-guard refusal and the broader store-suite timeout remain recorded. |
| Hindsight 0.10.2 | Chunk retain/recall, restart persistence, bank transfer and independent source/target deletion controls pass. | Supported no-LLM mode: two documents/facts, local embedding/reranker. No observations, knowledge pages, reflection or native coding-client capture acceptance. |
| agentmemory 0.9.29 | Ingestion stores 15 fixture records and native search returns results; both upstream evaluation attempts report 0/15 because of session-ID mapping. | Scores cannot measure backend quality. Effective keyless default is BM25-only unless the supported local embedding provider is explicitly selected. No evaluator edits or production replacement. |

The next deciding run requires a valid maintained evaluation path, current
production controls, ordinary native client capture, recovery and complete
cost observation. The candidate list is fixed for this wave; the winning
backbone remains unresolved.

The fresh [release review](../../../evidence/artifacts/memory-runtime-resolution-20260930/latestness.json) identifies ai-memory 2.5.0 as source-only; prior 2.4.2 execution keeps its original version. Hindsight remains server 0.10.2/integration 0.8.0 and is the fit-based recommended shared-native target. The [published coding comparison](../../../evidence/artifacts/memory-runtime-resolution-20260930/published-coding-evidence.json) strengthens that priority against no memory, while full-cost and matched-finalist acceptance remain open.

Provider quota interruptions continue through the existing [cross-session protocol](../../../docs/landscape-continuation.md#continue-after-a-provider-usage-limit) and the foundation/durable-memory queue. The manifest carries a compact resume message, native eligible reset preference, exact evidence pointers and freshness rule. [Native schema evidence](../../../evidence/artifacts/memory-runtime-resolution-20260930/provider-quota-capability.json) confirms installed Codex reset methods; this review did not query account allowance or redeem a reset.
