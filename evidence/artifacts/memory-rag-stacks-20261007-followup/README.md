# Memory/RAG source-review qualification (2026-10-07)

This new record resolves the three post-merge findings on #828. The
[original review](../memory-rag-stacks-20261007/review.json) remains unchanged;
the [machine-readable qualification](source-qualification.json) and the
[dated decision amendment](../../../docs/decisions/2026-10-07-memory-rag-source-stacks.md#amendment-2026-10-07-proposed-status-and-source-provenance)
carry the current interpretation.

1. **F1 (P2), proposed status.** The five architectures and their component
   roles are proposed source-review inputs to MEMORY-SCREEN. They preselect no
   memory-h2h winner, replace no independently owned measurement and select no
   memory owner for this host. The original October 6 policy citation remains;
   the separately directed memory screen and head-to-head consume this input.
2. **F2 (P2), provenance.** The earlier separate PageIndex benchmark revision
   remains unrecovered in the retained materials checked. A new primary check
   pins its [README](https://github.com/VectifyAI/PageIndex-OSS-Benchmark/blob/ad4c0b92970a6f4801f09ff2e647389e8f5874fa/README.md#L6-L15)
   at `ad4c0b92970a6f4801f09ff2e647389e8f5874fa`, read at
   2026-10-07T12:10:27Z. It supports the maintainer's
   published description of 62 questions over 34 PDFs, running-text facts only,
   with charts, tables, figures, counting, arithmetic and refused documents
   excluded. These are vendor scope and selection claims, not a new benchmark
   result or independent dataset validation. The amendment also links all 18
   original component pins directly.
3. **F3 (P3), execution states.** Installation and native-client smoke were
   **not performed in this review**; organic use was **not observed in this
   review**. References to tested Opik integrations name upstream CI as the
   actor. No full stack, model or comparative evaluation was executed here.

The source check does not backdate a benchmark revision, establish compatibility
with the separately pinned PageIndex implementation, or establish a ranking.
Original upstream failures and source pins remain available in the old review.
Artifact/schema/hash checks of this follow-up are structural validation, not
runtime acceptance; provider usage and net token savings remain unknown.
