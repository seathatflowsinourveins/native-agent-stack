# FOUNDATION capability catalog

FOUNDATION selects the general native workflow: clients, skills, owned workers,
source retrieval, memory, research, quality, applications, observation and recovery.
Start with the layer needed for the task in [manifest.json](manifest.json), then
read its scoped capability decision in [decisions.json](decisions.json). A default
is a selected way to do a task, not permission to install or activate every tool.

The catalog references 60 selected components through 39 capability decisions,
plus one separate Tavily integration candidate. It cites 63 relevant registered
receipts from the current 88-receipt inventory. These are coverage counts, not a
score of complete installation, execution or lifecycle acceptance.

| Layer | Purpose |
| --- | --- |
| Native clients | Signed-in native coding/research tasks and actual process activation |
| Instructions and skills | Short project rules and task-specific procedures |
| Workers | Bounded delegation, owned paths and independent acceptance |
| Isolation | Worktree ownership and selected enforced OS restrictions |
| Code navigation | Exact symbols, structural patterns and scoped source retrieval |
| Document retrieval | Named lexical corpora and supported document ingestion |
| Semantic RAG | Project-scoped conceptual code retrieval and local embeddings |
| Durable memory | Approved cross-client decisions, continuity and scoped restore |
| Web research | Selected browser, literature and current-source operations |
| Token efficiency | Adequate context representations and honest usage accounting |
| Quality and evaluation | Behavioral oracles, negative cases and independent review |
| CI and supply chain | Publication checks, security controls and dependency identity |
| Scheduling and supervision | Owned process deadlines and checkpointed job continuation |
| Hosting and services | Typed local applications, databases and selected MCP services |
| Recovery and portability | Exact restore inputs, session continuity and lifecycle limits |
| Observation and inference | Bounded telemetry, usage and optional inference trials |

Each layer records its purpose, selected approach, activation condition, lifecycle
scope and next actionable gap. Decisions join actual `component_ids` and
`evidence_ids`; they retain an explicit `evidence_scope`, limitations and activation
rule. `accepted_within_scope` describes the named capability only. Partial,
source-review and pending decisions remain distinguishable from acceptance.

Pins remain in [the stack manifest](../../manifests/stack.json). Original receipt
claims, evidence classes, paths and limitations remain in
[the evidence manifest](../../manifests/evidence.json). Lifecycle `stage_refs` point
to the exact status in [the component matrix](../../blueprints/token-native-focus/saturation-audit.json);
they do not duplicate its commands, stage scope or receipt content. Read those
canonical details before reusing acceptance. Unlisted stages and the explicit
`lifecycle.unknown` field do not become successful by implication.

The [broad decision index](../us-equities/decision-index.json) remains the shared
research inventory at its existing path. Discovery lists, candidates and older
[foundation/memory](../us-equities/foundation-memory.json) or
[agent/operations](../us-equities/agents-operations.json) source reviews remain
available. Their directory placement and reviewed source pins do not supersede
the currently selected component pin or qualify an entire repository.

The manifest explicitly leaves LEAN, Alpaca, skfolio, EdgarTools and the currently
financial-only DuckDB/pandas claims in the [US-equities domain](../us-equities/README.md).
Some domain-located fixtures demonstrate reusable operations such as process-tree
termination, dependency inventory or state restore. A FOUNDATION decision cites
only that operation; it does not import strategy, market-data, broker or trading
acceptance. The Tavily entry references its
[existing source/integration receipt](../../docs/ecosystem/tavily-receipt.json)
and leaves current intended-host native CLI integration pending reconciliation.
It does not erase earlier dated observations or create an adopted component.

The three current priorities are:

1. Keep general capabilities and financial-domain decisions separate, with
   explicit claim scope. This catalog addresses that structure; maintain the
   references when evidence changes rather than migrating the broad inventory.
2. Qualify cancellation, abrupt crash and resume of an owned writing worker.
   Existing local termination, individual session resume and checkpointed jobs
   remain useful narrower results.
3. Qualify independent off-host restore with separately available key recovery,
   and scheduled-service acceptance after reboot. Same-host restore and ordinary
   stop/start do not close these gaps.

Use [the convergence guide](../../docs/convergence-architecture.md) for the work
sequence and [the lifecycle guide](../../adoption/lifecycle.md) for selected native
operations. Keep failed attempts, unknown usage and new-host limits intact.
The newer vLLM startup failure, failed gateway inference/compression attempts,
unverified live HUD and TOON expansion remain counterexamples, not successes.

Validate references without installing tools, calling providers or replaying
native acceptance:

```sh
python3 scripts/validate_foundation.py --root . --json
python3 -m unittest tests.test_foundation_catalog
```

The validator checks the 16 layers, unique identities, component/evidence joins,
source paths, explicit scope/limitations, canonical lifecycle statuses, candidate
separation and scoped supersession. It rejects copied pin/receipt fields. A later
decision may supersede only an earlier decision for the same capability and
component scope, retaining the old record with a reason and scope. Structural
validation cannot certify the truth or adequacy of a prose claim; review the cited
receipt and its limitations before changing an adoption decision.
