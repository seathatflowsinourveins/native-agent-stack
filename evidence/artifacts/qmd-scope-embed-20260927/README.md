# qmd catalog index: embeddings, scope and an in-scope retrieval A/B (NativeStack workstation, 2026-09-27)

The named index `native-agent-stack-catalog` (qmd 2.8.3) indexes the `native-agent-stack-live` checkout. The work was agreed with `token-efficiency-evidence-cards`, which owns qmd's cards and recipes. It is recorded for #381 Amendment 3 as a pre-run tool configuration. Paths are masked: home as `~`, scratchpad as `$SCRATCH`.

## What changed on the host

1. **Embeddings, 16:19:06Z–16:25:57Z.** `qmd --index native-agent-stack-catalog embed` embedded 744 chunks from 122 documents in 6m 50s, with `embeddinggemma-300M-Q8_0` (sha256 `b5ce9d77…0d63`, 333,590,944 bytes). Before: 0 vectors (`status-before.txt`). After: 744 (`status-after.txt`).
2. **Scope.**
   - `collection add` created `foundation-adoption` (`adoption/`, 23 docs) and `foundation-docs` (`docs/`, 124 docs) at about 16:42Z.
   - `ignore: ["ecosystem/**"]` was then added to the index's YAML. Per-collection ignore is YAML-only (qmd v2.8.3 README L755).
   - `update` at 16:43:04Z removed `docs/ecosystem/README.md`, leaving 123 docs (`scope-update.out`).
   - `embed` ran 16:43:11Z–16:55:44Z: 1,506 chunks from 146 documents in 12m 32s.
   - Final state: 268 documents and 2,250 vectors in 4 collections (`status-after-scope.txt`).
   - The prior YAML and SQLite are backed up privately under the host's state directory.
3. **Device: CPU.** qmd's loader calls node-llama-cpp `getLlama({gpu:"auto"})` (qmd `dist/llm.js` L634-650). From qmd's own package it resolved `{"gpu":"vulkan","devices":[]}` (`device.mjs.txt`), so the RTX 4090 was not used. It was left that way: the GPU serves production models.

## Why scope first

E1's qmd retraction (failure mode `wrong_document`) was a scope failure. The answering document, `adoption/update.md`, was outside the two indexed collections. On E1's own query every arm scored 0 of 5, before and after embedding (`lex-search*.json`, `vsearch-post.json`, `query-*-embed.json`).

## In-scope A/B (frozen before any run)

**Protocol**
- GPT-6 (astra, max) authored 10 queries from the markdown files without running qmd: 3 lexical, 4 paraphrase and 3 conceptual, at least 2 per collection.
- Every expected document was verified by a grep across all 268 files.
- The queries are disjoint from #381's 7 qmd tasks (`prereg381-qmd-tasks.json`) and from E1's query.
- Frozen at 16:57:28Z: `queryset-frozen.json`, sha256 in `queryset-frozen.sha256`. The runner (`run_ab.py.txt`) asserts the hash.
- Run 16:57:45Z–17:16:45Z.

**Results (`ab-results.json`)**

| arm | hit@1 | hit@5 | MRR@5 | median s |
|---|---|---|---|---|
| lex (`qmd search`, raw question) | 1/10 | 1/10 | 0.10 | 0.2 |
| vec (`qmd vsearch`) | 7/10 | 9/10 | 0.783 | 7.9 |
| hybrid (`qmd query`) | 5/10 | 10/10 | 0.725 | 121.4 |

**Limits**
- n=10 synthetic questions.
- The lex arm sent raw questions, not the keyword queries an agent would write.
- Hybrid runs on CPU.

This is directional evidence for embeddings on; it is not a lane acceptance.
