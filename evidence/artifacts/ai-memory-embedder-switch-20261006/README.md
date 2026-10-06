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
