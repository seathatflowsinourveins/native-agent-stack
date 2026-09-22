# Original-source adjudication of independent findings

These checks follow the sealed Codex source report. A separate reader inspected
the decision-relevant implementation and upstream test assertions. No candidate
installation, test execution, broker call or model trial occurred in this review.

## code-memory: conditional portability comparison

At `5a8db166ca11a90c093ba4a9a54d266cde756f54`,
[code-memory](https://github.com/kapillamba4/code-memory/tree/5a8db166ca11a90c093ba4a9a54d266cde756f54)
1.0.33 implements SQLite FTS5/vector search, reciprocal-rank fusion, AST
symbols/references and optional reranking. This can simplify deployment compared
with separate retrieval/inference services. Its dependency contract requires
Python >=3.13 and sentence-transformers/PyTorch-related packages. No measured
resource, retrieval or maintenance advantage was established.

The accepted SocratiCode source already has
[dense/BM25 fusion](https://github.com/giancarloerra/SocratiCode/blob/2218f25153d0f3f4a76ee240a5643dbc873e80be/src/services/qdrant.ts#L870-L973);
the candidate's [hybrid ranking](https://github.com/kapillamba4/code-memory/blob/5a8db166ca11a90c093ba4a9a54d266cde756f54/code_memory/queries.py#L104-L161)
therefore does not establish a missing retrieval capability.

Code is MIT, while the default Jina embedding weights declare
[CC-BY-NC-4.0](https://huggingface.co/jinaai/jina-code-embeddings-0.5b/blob/4db235132dafbe56a8b9c5f59b59795ecf58a4a7/README.md).
The [loader](https://github.com/kapillamba4/code-memory/blob/5a8db166ca11a90c093ba4a9a54d266cde756f54/code_memory/db.py#L122-L144)
enables remote model code and does not pin a model revision. Select and pin an
appropriate model separately before a reproducible comparison; the repository's
license does not describe the weights' terms.

Two source-level freshness concerns need actual reproduction: previously indexed
files that become ignored while remaining on disk are not pruned; a corpus with
no remaining indexable code files returns before stale cleanup. The inspected
[collection/early return](https://github.com/kapillamba4/code-memory/blob/5a8db166ca11a90c093ba4a9a54d266cde756f54/code_memory/parser.py#L367-L386),
[pruning](https://github.com/kapillamba4/code-memory/blob/5a8db166ca11a90c093ba4a9a54d266cde756f54/code_memory/parser.py#L490-L500)
and [caller](https://github.com/kapillamba4/code-memory/blob/5a8db166ca11a90c093ba4a9a54d266cde756f54/code_memory/server.py#L457-L514)
support these bounded implications. They are not retained runtime failures.

Exact-head [CI passed on three platforms](https://github.com/kapillamba4/code-memory/actions/runs/26167401616);
the separate [binary upload failed after builds](https://github.com/kapillamba4/code-memory/actions/runs/26167616153).
The sampled [tool tests](https://github.com/kapillamba4/code-memory/blob/5a8db166ca11a90c093ba4a9a54d266cde756f54/tests/test_tools.py#L18-L131)
primarily check validation and response shape, not semantic retrieval quality.

**Decision:** retain the accepted route; add a conditional portability comparison.
Freeze both implementations, permitted model revisions, representative queries
and source/line ground truth. Compare quality, complete returned context, cold/warm
latency and memory, including edits, deletes, new exclusions, deleting every code
file and restart. Require no stale/excluded results. A material deployment benefit
with required quality/lifecycle parity can justify a different host profile.

## NautilusTrader: two ineffective variant checks

At source `82b66fee382086c803e27b9fd5c06f94d24d2831`, two risk tests assert event
count but discard the Boolean returned by `matches!`:
[invalid price precision](https://github.com/nautechsystems/nautilus_trader/blob/82b66fee382086c803e27b9fd5c06f94d24d2831/crates/risk/tests/risk_engine.rs#L169-L170)
and [maximum notional](https://github.com/nautechsystems/nautilus_trader/blob/82b66fee382086c803e27b9fd5c06f94d24d2831/crates/risk/tests/risk_engine.rs#L245-L246).
Those expressions do not enforce the event variant. Count coverage remains, and
other tests assert denial and reasons for
[precision](https://github.com/nautechsystems/nautilus_trader/blob/82b66fee382086c803e27b9fd5c06f94d24d2831/crates/risk/tests/risk_engine.rs#L1667-L1687)
and [notional limits](https://github.com/nautechsystems/nautilus_trader/blob/82b66fee382086c803e27b9fd5c06f94d24d2831/crates/risk/tests/risk_engine.rs#L4662-L4677).

The same two test bodies occur in
[v2.0.0rc5 source](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/risk/tests/risk_engine.rs#L109-L247).
This checks release source; it does not prove the installed binary's provenance
or a production risk-engine defect. An appropriate targeted check would wrap
the expressions in `assert!`, run the exact upstream tests, then require a
single wrong-variant event mutation to fail. Denial reason and absence of
forwarded execution commands deserve explicit assertions.

**Decision:** retain the destination with the comparison open. LEAN's
[IBKR plugin](https://github.com/QuantConnect/Lean.Brokerages.InteractiveBrokers)
and [Alpaca plugin](https://github.com/QuantConnect/Lean.Brokerages.Alpaca) strengthen
its integration case. The [LEAN CLI](https://www.quantconnect.com/docs/v2/lean-cli/key-concepts/getting-started)
has paid-organization and local Docker conditions distinct from the open-source
engine. Neither source coverage nor these test defects settle engine correctness,
broker operation or strategy performance. Use an independent accounting oracle
and broker-specific paper/recovery acceptance on the same frozen inputs.
