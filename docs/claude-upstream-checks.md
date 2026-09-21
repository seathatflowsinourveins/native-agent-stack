# Live Claude: retained upstream checks, September 21

The [per-repository report](ecosystem/claude-upstream-checks.html) records the
corrected native commands and returned results from live Claude's local run.
It covers **38 rows: 14 bounded functional checks, 18 readiness checks and six
version/help checks**. All recorded commands returned zero; that is not 38
functional E2Es. The [structured results](../evidence/artifacts/claude-upstream-checks-20260921/results.json)
preserve each row's evidence class, command, exit, duration, displayed excerpt
and original stdout hash. The explorer also attaches the three reviewed native
dashboard screenshots and the [projection provenance](../evidence/artifacts/claude-upstream-checks-20260921/provenance.json).

The local embedding check called the configured vLLM endpoint and returned the
expected Nemotron embedding model, 2,048 dimensions, norm 1.0 and eight reported
prompt tokens. It validates that selected local call. The earlier wrong-port
probe's fallback text was incorrectly accepted; that superseded observation is
retained in the corrected row and original host records. No service or model
reinstallation was needed.

Other functional rows include exact TOON recovery, selected code/document
retrieval, a source-file pack, upstream report commands and retained-output
tests. A savings-report command is functional only as a reporting operation;
it does not prove saved provider tokens. Nautilus imports, client login/help,
MCP discovery and service health remain readiness checks. Reuse the separately
accepted [native Claude profile](../recipes/claude-native-ultracode.md),
[Claude-to-Codex review](../recipes/claude-codex-foreground-review.md),
[memory/RAG lifecycle](native-memory-rag-lifecycle.md),
[QMD comparison](../evidence/artifacts/foundation-rd-20260921/qmd-comparison.json)
and [engine receipts](../blueprints/us-equities/engine-nautilus/README.md) for their
own recorded scopes.

## Correction and independent verification

The native runner now propagates pipeline failures, rejects the observed
failure-masking command shapes, and retains complete stdout/stderr privately.
Ten synthetic regression tests passed. Independent verification checked all
144 original stream files, all 72 full stdout hashes and displayed excerpt
hashes, and the source-to-excerpt comparisons. Seven stdout excerpts are
truncated. Original streams are retained privately with their individual hashes;
the published record contains bounded sanitized excerpts, not full raw output.

The public projection removes private raw references and local process/session
identifiers, substitutes host-path placeholders, and preserves a source hash for
the native report. It replaces host-only receipt references with matching public
references where available; omitted references do not become public acceptance.
Repository redirects are resolved and the incorrect SocratiCode URL is repaired.
The supporting `uv` row does not add a new selected component to the 68-component
catalog. This report is dated source-host evidence, not a runnable installation
spec for another PC. Use the existing portable adoption recipes for setup.

## Lifetime and dashboards

RTK, Headroom and Context Mode estimates retain their own scopes and retention
limits. The three Context Mode process snapshots overlap; do not sum them or
attribute their common history to this task. Native client usage, telemetry,
artifact comparisons and avoided-token estimates are different quantities.
Neither this report nor the screenshots establish causal provider savings.

The six-hour Grafana view legitimately has empty SDK panels. The 72-hour view
shows 186,019 reported SDK tokens and four receipts without usage; it is a dated
range, not complete provider billing or a lifetime total. The lifetime-page
screenshot is also dated and does not substitute for refreshing native counters.
The [R&D readiness handoff](foundation-rd-readiness.md) remains the next-build
contract; this report adds observations without closing unrelated broker or
strategy gates.
