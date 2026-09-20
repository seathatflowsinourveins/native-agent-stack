# Evidence and native replay

The public evidence manifest lists each receipt, its claim, limitations and covered components. Its file list records SHA-256 and byte length for every exported receipt and fixture. These hashes establish integrity of the published bytes; they do not independently authenticate a provider or turn a recorded result into a new run.

The [September 20 token-practice audit](token-practice.md) records four accepted
native coding trials with mixed observed usage differences, ten exact retained-artifact
comparisons and explicit native counter scopes. Its sanitized aggregate receipts
supersede older summaries only for their stated scope.

## Evidence levels

| Kind | Meaning | What validation establishes |
| --- | --- | --- |
| `native_model_e2e` | A real native client called tools and produced a task result | The receipt preserves outcomes/usage; CI checks integrity, not account inference |
| `native_cli_e2e` | An upstream executable processed useful input and returned an observed result | Recorded behavior, not necessarily an LLM-driven invocation |
| `artifact_measurement` | Explicit input/output text was counted with a named tokenizer | The public artifact pair can be recounted exactly |
| `historical_inventory` | Dated evidence/limits imported from the reviewed local inventory | A bounded provenance statement, not a new acceptance run |
| `compatibility_attempt` | A new release was installed or executed with a recorded success/failure | Failed attempts remain visible and cannot certify the active runtime |

Original raw native streams and account data remain private. Receipts publish selected factual fields and source-artifact hashes, omit personal paths/session identifiers, and distinguish observations from interpretations. This is evidence transparency with a privacy boundary, not independently attested provider telemetry.

## Native workflow results

- [LEAN cost sensitivity](../blueprints/us-equities/execution-realism/receipt.json): three native fixed-order simulations completed with distinct fee/slippage assumptions and reconciled serialized cash; full execution realism remains open.
- [Temporal snapshot selection](../blueprints/us-equities/point-in-time/receipt.json): native DuckDB/Parquet exercised synthetic revisions, universe changes, feed/adjustment scope and integrity through 11 command exits; actual historical source availability and entitlement remain unaccepted.
- [Offline Alpaca guard](../blueprints/us-equities/order-contract/receipt.json): native request-model serialization and strict local rejection under network isolation; no client, broker connection, advanced instructions or replace/cancel acceptance.

- `native-context-memory`: historical native Context Mode/Serena/RTK work, plus fresh Context Mode/memory startup on current clients. PreCompact was not deliberately triggered.
- `native-memory`: both clients retrieved a scoped durable decision page; native lifecycle observations and a cross-client handoff were recorded. Consolidation/backfill were not enabled.
- `native-rag`: both clients retrieved relevant code through native SocratiCode; real local Nemotron vectors populated Qdrant; an automatic watcher changed persistent payloads after add/update/delete with no tool-triggered catch-up.
- `desktop-cli-workflows`: this active Codex Desktop task passed QMD search/get, graph search/trace, and a visually inspected local browser interaction. The separate native CLI quota limitation remains explicit.
- `portable-cli-artifacts`: upstream ShellCheck, Difftastic, MarkItDown, ast-grep, TOON and Repomix processed the public fixtures; initial failures/corrections are retained.
- `native-cli-gaps`: the additional Claude document/static-graph/browser run passed. Codex hit its account limit before tool use; no token usage is invented for that failed attempt. Claude's 126-word final exceeded the requested 120-word limit, so runtime acceptance and complete instruction adherence are separate.
- `runtime-tools`: Gitleaks' redacted 22-commit scan and SRT's filesystem behavior. Network policy was configured but not separately exercised.
- `worktrunk-list`: native worktree inventory on the publication repository, with machine paths omitted.
- `component-history`: remaining selected CLI/reference tools retain their original host-specific proof. Optional live HUD, outer Claude-to-Codex slash command and native promptfoo use are not claimed as completed.

- `native-observability`: actual Codex/Claude client usage, two completed SDK tasks with a separately validated receipt lane, six native services, seven scrape targets, six restart checks, a rendered dashboard and firing/resolved local notifications. The native SDK histogram remains unobserved; existing Desktop exporter activation remains separate.

- `native-observability-followup`: a fresh Astra SDK task used Context Mode, automatically published a result receipt and exported matching native histogram categories. Native WSL host metrics also arrived. Direct Desktop memory/RAG/bridge operations worked, while parent Desktop OTLP and direct Context Mode discovery remained unobserved.

- The later [Desktop restart receipt](../observability/restart-receipt.json) supersedes those two pre-restart gaps: 11 direct Context Mode tools were discovered and correlated parent logs arrived. Earlier receipts remain dated evidence, not the current activation summary.

- [Portable SDK adoption](../adoption/receipt.json): native uv recreated the accepted 36-package dependency set in a fresh prefix and reinstalled it without cache using required hashes. Local data/SDK checks and native account readiness have separate outcomes; this is not a second physical machine or a new model-inference result.

- [Paired native adoption](../adoption/paired/receipt.json): subsequent native sign-in restored readiness, and fresh LEAN/Dagu/DuckDB/Astra/Claude execution completed. Astra used 20,776 tokens and Claude 16,293; matching native telemetry reconciled. The scoped account/pair gate is resolved, while unrelated data, hosting, broker and net-savings gates remain open.

## Reproduce useful native behavior

Configure your own project and client through the [native recipes](../recipes/README.md). Use one retrieval lane for a question: exact code in rg/Serena, conceptual code in SocratiCode, Markdown in QMD, durable decisions in ai-memory, historical transcripts only in explicitly scoped archive retrieval.

For local document/browser checks, the repository includes `fixtures/rag-note.md` and `fixtures/greeting.html`. Keep an isolated browser session and close it when finished. A graph check requires an explicit index of your project; a semantic watcher check requires a live native MCP process and the configured local model/vector services. Hosted native agent runs consume your own allowance; no API key or subscription route is supplied by this repository.

The original commands are parameterized in component manifests and recipes. Variables such as `${PROJECT_ROOT}` and `${MCPORTER_CONFIG}` require explicit values. They are shell notation in documentation, not a claim that every native JSON/TOML format expands environment variables.

## Token measurements

The original full code file contained 2,731 o200k_base tokens; the complete returned SocratiCode result, including preamble, contained 491. The difference was 2,240 tokens, 82.0212%. The public source fixture replaces personal path literals and measures 2,730 → 491 instead. Both facts are retained; a public recount is not presented as a byte-identical original run.

The historical RTK artifact was 533 → 176 tokens; the selected paper excerpt was 18,533 → 483. These are lossy retained-text comparisons against a whole-input counterfactual. They omit prompts, tool schemas, skill reads, coordination and retries. They do not establish whole-provider savings or subscription billing reductions.

Native Codex input includes its cached-input subset; Claude's ordinary input, cache creation and cache reads are separate categories. Reasoning/thinking is an output subset where reported. Do not sum these conventions blindly or combine cumulative account totals with per-task counters.

The [observation artifact pair](../observability/README.md#token-efficient-operation-and-accounting) recounts to **188,769 → 500** tokens with upstream `gpt-tokenizer3.4.0` and `o200k_base`. The selected ten token series answer one operational question; other metric data is intentionally excluded and retained in the source. Run `node scripts/recount-tokens.cjs --observability` with the documented isolated tokenizer prefix. This is not net provider savings.

## CI boundary and costs

The workflow uses a standard Ubuntu GitHub-hosted runner, read-only repository permissions, a commit-pinned checkout with persisted credentials disabled, and local evidence validation/tests. It performs no model call, credential login, artifact upload, cache save, service deployment or scheduled job. Public standard-runner usage is free under the checked [GitHub billing policy](https://docs.github.com/en/billing/concepts/product-billing/github-actions); larger runners and storage have separate rules.

A successful CI result establishes repository consistency and validation behavior. It does not certify that a public runner reproduced your local GPU, paid-plan agent session, live HUD or all optional integrations.
