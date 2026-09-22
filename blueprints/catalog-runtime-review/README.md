# Native runtime review of the grand catalog

The September 21, 2026 review used the existing native Codex SDK and Claude CLI
against a frozen 20-layer packet from
`dac2d1a3f880c04f6afadebe8bf3a251a64ab605`. No new hosted service or paid deployment
was needed. A one-off Dagu run supervised the original branches; it recorded
their failures correctly. The final successful Claude pass used the native CLI
separately, with the same packet and bounded original-source excerpts.

| Actual attempt | Returned result | Reported token sum |
| --- | --- | ---: |
| Codex Python SDK, Astra | Model at capacity; no verdict | Unknown |
| Claude Opus 5, high requested effort, source tools | 29 source calls; exceeded 18-turn cap | 1,163,219 |
| Claude corrected tool-free pass | HTTP 500, `is_error=true`; no verdict | 0 |
| One transient-error retry | Completed one turn in 103.389 seconds | 48,229 |

The final report covered all 20 layer IDs exactly once and returned
**ready as a recipe baseline**. High effort was requested; resolved effort was
not exposed. The sums include input, cache creation, cache reads and output;
the [native record](../../evidence/artifacts/catalog-runtime-review-20260921/native-review.json)
keeps these categories separate. They are not a dollar cost, unique context size
or savings measurement. Failed attempts remain part of the record.

The coordinator checked the six qualifications against source evidence:

1. Preserve the dated baseline: 8 retain, 1 adjust, 11 keep-but-compare decisions.
2. Memory restore involved one ordinary decision and 51 System pages.
3. Native Codex task consolidation is distinct from ai-memory's internal LLM
   consolidation, which was disabled in that test.
4. DeerFlow acceptance covers one embedded ACP task. Its tested `read-only`
   preset mapped to `workspaceWrite/on-request`, so it did not enforce read-only
   filesystem access or qualify the full service.
5. The exercised Codex Python SDK is distinct from conditional OpenAI Agents SDK.
6. Clean-prefix package installation does not cover all foundation components or
   transfer acceptance to a new PC.

These qualifications are now explicit in the
[handbook](../../docs/grand-catalog-handbook.md). Some clarify existing policy;
they are not six newly discovered implementation defects. The native report
reviewed the frozen baseline, before the subsequent 16-repository source-quality
refresh and HTML changes. Those changes receive separate integration checks and
independent code review.

The [receipt](../../evidence/receipts/catalog-runtime-review-20260921.json) links
actual commands, immutable source hashes, returned findings, usage and failures.
The [scoped experiment record](experiment.json) preserves all four inference
attempts using the repository's convergence evidence contract.
The [executed prompt](../../evidence/artifacts/catalog-runtime-review-20260921/successful-claude-prompt.txt)
and its frozen source packet are retained with one installed-skill path replaced
by a placeholder. [Input provenance](../../evidence/artifacts/catalog-runtime-review-20260921/input-provenance.json)
records original and public hashes, the replacement and exact-byte verification.
The published prompt and TypeSafe context also add a terminal newline, recorded
in that provenance; remove it before reconstructing the original bytes.
No successful Codex verdict or cross-family agreement is claimed. Review does
not benchmark repository quality, certify all upstream tests or accept a new PC.
Use the existing runtime that fits a bounded check; escalate to a full research
service only when it closes a demonstrated acquisition, state or recovery gap.
