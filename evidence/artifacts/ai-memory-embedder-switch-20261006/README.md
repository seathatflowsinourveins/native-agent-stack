# ai-memory Nemotron embedder switch — 2026-10-06

The command-center executor accepted this NativeStack2604 switch at
2026-10-06T16:45:58Z. [receipt.json](receipt.json) is the unchanged sanitized
native execution receipt, SHA256
`8624a287a3df356e4ddabfdd0975ad4b93ca85d83ad57e9bbd36edc6df64339b`.
Verify it with `sha256sum -c SHA256SUMS` from this directory.

The initial backfill embedded331/331 pages with no failures in78.632s.
At acceptance335/335 latest pages had the configured4096-dimensional Nemotron
identity, with no incomplete scopes or failure rows. The fixed known-answer
set contains29 usable targets: hit@5 stayed29/29, hit@1 improved23→27,
and every target used the vector stream. Both literal prefixes were proved
with cosine differences at most2e-6. p50 latency changed184→54ms.

Evidence class is native execution by the named executor, with private raw
files retained. This publication is not a rerun or an upstream test result.
The receipt's acceptance-time Gate3 is PARTIAL and non-blocking: Codex→Claude
passed late after native login; Claude→Codex did not run post-switch because
its source session hit429, and the missing Claude prompt-capture defect was
then open. The CC later applied the upstream capture installer; a fresh
Claude→Codex follow-up passed recall and the marker/fact association control.
The strict no-canary-fact-text control still failed. The dated
[decision](../../../docs/decisions/2026-10-06-ai-memory-nemotron-embedder.md)
records that separate follow-up without changing this receipt. The
manager-level environment check remains an untested boundary.

Only the receipt is published. Questions, page paths, session identifiers,
canary text, before/after results and backups remain private. Backups are
retained until at least2026-10-13; the optional purge of227 superseded MiniLM
rows was not run. See the [decision](../../../docs/decisions/2026-10-06-ai-memory-nemotron-embedder.md)
for source pins, alternatives and the comparison that would overturn it.

## Addendum (2026-10-06): control meaning and later recall evidence

The raw strict text-absence flag above remains false. The command-center
ruling treats it as a text-presence observation, not a defect or leak gate:
nearby vector hits in the small scratch corpus can include canary facts.
The marker/fact association control, `control_clean`, is the actual leak
check. Its passing result does not assert strict text absence.

The later long-prompt smoke failed recall despite intact prompt capture.
After the documented optional SessionEnd consolidation was configured, one
authorized long-prompt rerun passed recall and `control_clean`; strict text
absence remained false. The dated
[decision addenda](../../../docs/decisions/2026-10-06-ai-memory-nemotron-embedder.md#addendum-2026-10-06-long-prompt-failure-and-consolidation-rerun)
record the failed and passing private receipt hashes, source citations and
the separate CC cleanup manifest. The acceptance-time values and this
published receipt are unchanged. The memory KEEP ruling and upstream
re-drive trigger are recorded there as subsequent decisions.
