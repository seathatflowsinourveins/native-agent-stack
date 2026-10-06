# Qmd lexical supersession (2026-10-06)

Status: the command-center final local-model ruling retired qmd's embedding role.
Backend qualification is recorded; client cutover and final cleanup remain
command-center owned. This new record is the portable companion to the existing
dated lane supersession record, preserving its decision and evidence boundaries.

The [original 8B selection](https://github.com/seathatflowsinourveins/native-agent-stack/blob/d70c46a625c2b51758967afd35231da4866ebf65/docs/decisions/2026-10-06-qmd-cpu-embedding-upgrade.md)
remains historical. Its decided text was restored under A2, and retirement is
recorded in an appended [dated amendment](2026-10-06-qmd-cpu-embedding-upgrade.md#amendment-2026-10-06-retired).
The original file was 8,061 bytes with SHA256
`25e5a665e2bb87a1bce16dd355dc465d0e8bbfa9b574e5e154c413c3f773e192`.

Semantic catalog Markdown retrieval is assigned to SocratiCode on the shared
Nemotron endpoint. Qmd keeps lexical retrieval, query expansion, and its own
upstream default reranker as a named exception. The proposed 8B AFTER acceptance
and client argument switch are withdrawn; the incomplete index is not accepted.

The native lexical backend smoke recorded 425 documents, zero vectors, zero
excluded ecosystem documents, pinned kept-model hashes and rank header, and its
declared expected document at rank 1 with actual reranking. The preceding failed
credential-query output remains separate. Native operations and independent
read-only observation qualify this bounded integration, not semantic/ranking
quality or both-client acceptance. The private receipt SHA256 is
`619f5df78d1d45c2126332c9161f525353fb60bc6410cf1f73413289717cfa91`;
no receipt, log, benchmark row or measured value is changed by this record.

Kept upstream files are the
[reranker](https://huggingface.co/ggml-org/Qwen3-Reranker-0.6B-Q8_0-GGUF/tree/a02f48bb4f057028298c21fa033da2b30d7742d5)
and [expansion model](https://huggingface.co/tobil/qmd-query-expansion-1.7B-gguf/tree/7816de0b72572c6c860ca1eddf97ba9e7fb8cc65),
used through [qmd 2.8.3](https://github.com/tobi/qmd/tree/facd35e01359e59d938bc9418e93fb9318addee3).
The amendment retains their observed hashes and header evidence unchanged.

Future embedding/reranker discovery admits any vendor and candidates without
board rows, including contextual encoders. The one-card
[Perplexity preview review](https://huggingface.co/perplexity-ai/pplx-embed-v2-context-9b-preview/blob/b667039ee8b438a6350fbc91bbcecd86f9d363ba/README.md)
establishes a candidate interface, not superiority over the kept endpoint.
A supported runtime/encoding contract and task-relevant quality/resource
acceptance would be required to overturn the current retrieval direction.

CC owns final holder checks, deletion/unregistration, and both-client
configuration application/read-back. Historical artifacts and decided text stay
intact; further decision changes use dated addenda or supersession links.
