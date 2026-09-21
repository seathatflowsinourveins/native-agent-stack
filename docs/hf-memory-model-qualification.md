# Current Hugging Face models for memory and retrieval

Reviewed September 21, 2026 using native `hf` 1.32.0, revision-pinned model
cards, the running embedding service and upstream examples. Model release dates,
published benchmark scores and local runtime acceptance are different evidence.

The current code-RAG model is **NVIDIA Nemotron-3-Embed-1B-BF16**, from the
July 16, 2026 family. It is a current, capable retrieval model, not a demonstrated
universal winner. Shared ai-memory uses **MiniLM as a supported compact baseline**;
it must not be labeled the latest SOTA model.

## Which model is selected, and why

| Model | Role on this PC | Evidence and limitation |
| --- | --- | --- |
| [Nemotron 3 Embed 1B BF16](https://huggingface.co/nvidia/Nemotron-3-Embed-1B-BF16) | Active SocratiCode embedder, 2,048 dimensions | All 15 upstream repository files matched the selected revision. The native model-card example and existing OpenAI-compatible route returned the expected first-ranked documents for all four examples. |
| [Nemotron 3 Embed 8B BF16](https://huggingface.co/nvidia/Nemotron-3-Embed-8B-BF16) | Quality candidate, not installed | NVIDIA reports RTEB 78.46 versus 72.38 for 1B on the same 16-task table. BF16 weights alone need about 14.81 GiB; no local quality/latency or serving qualification establishes it as a better default on this shared GPU. |
| [all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) | Active ai-memory local provider, 384 dimensions | All three files required by the upstream loader matched HF checksums. This is an older compatibility baseline with symmetric encoding. |
| [EmbeddingGemma](https://huggingface.co/google/embeddinggemma-300m) | Unadopted compact candidate | Requires distinct retrieval prompts and gated model/config access. Its published MTEB scores use different benchmark scopes and cannot be compared directly with NVIDIA's RTEB table. |

The local GPU is an RTX 5090 Laptop with 24,463 MiB total memory. Capacity alone
does not prove that a larger model meets latency, context or concurrent-work
requirements. The running 1B service uses **4,096 tokens**, although its model
card supports 32,768. Do not advertise the model-card limit as the live limit.

NVIDIA's pinned card explicitly recommends **vLLM 0.25.0** for BF16 `/v2/embed`.
That strengthens the existing WSL compatibility decision; a newer runtime version
alone is not a reason to replace this documented native combination.

## Actual upstream commands and returned results

These commands refer to the selected native installation. Substitute explicit
paths on another PC; the revision identifies the reviewed files.

```sh
hf version --format json
hf models info nvidia/Nemotron-3-Embed-1B-BF16 --revision c0c9fea93ea424587517f2c59e20db9f1d6bf615 --format json
hf cache verify nvidia/Nemotron-3-Embed-1B-BF16 --revision c0c9fea93ea424587517f2c59e20db9f1d6bf615 --local-dir "$MODEL_DIRECTORY" --format json
hf download nvidia/Nemotron-3-Embed-1B-BF16 README.md --revision c0c9fea93ea424587517f2c59e20db9f1d6bf615 --local-dir "$EVIDENCE_DIRECTORY/model-card" --format json
curl --fail-with-body http://127.0.0.1:8231/v1/models
```

The HF verification returned `checked: 15`. Its warning about 33 extra local
files was traced to `.cache/huggingface/` download metadata, locks and tree cache;
all upstream files were present. For MiniLM, the verifier returned `checked: 3`
and reported 27 omitted upstream files. ai-memory's checksum-pinned local loader
uses those three files; the other repository formats were not installed. These
are scoped model-file checks, not a strict byte-for-byte directory mirror.

The exact Python example under NVIDIA's **Recommended Retrieval Endpoint** was
executed with only `localhost:8000` changed to the existing `127.0.0.1:8231`.
It returned:

```text
Similarity scores:
          d[0]      d[1]      d[2]      d[3]
q[0]    0.8113    0.0253    0.0003   -0.0311
q[1]    0.0448    0.6471   -0.0514    0.0383
q[2]   -0.0099   -0.0410    0.6472    0.1007
q[3]   -0.0220    0.0216    0.1207    0.7691
```

Each query ranked its intended document first. The separately exercised
`/v1/embeddings` route used the same upstream inputs with `query: ` and `passage: `
prefixes. It returned eight normalized 2,048-dimensional vectors, the same four
first-ranked documents and **336 input tokens consumed**. Those tokens are not
savings. Small score differences between routes and NVIDIA's rounded reference
remain visible; this is example-level integration acceptance, not a rerun of RTEB.

## Why the memory model was not silently replaced

ai-memory 2.3.2's local loader fixes MiniLM and its checksums. Changing a model
name in configuration does not turn it into a general HF loader. Its generic
OpenAI-compatible provider also lacks separate query/document instructions.

The upstream embedding trait has `embed_query`, but the reviewed MCP query
call site invokes generic `embed(query)`. For Google's provider, that generic
method delegates to document encoding. The same call was found on the examined
current main commit. Merely switching to a newer asymmetric model would therefore
not establish a correct native retrieval path. The symmetric MiniLM profile
avoids that particular distinction; it does not become SOTA through compatibility.

Memory pages are embedded as individual documents. Compatibility-mode truncation
uses a hard 8,000-byte ceiling, not model-aware tokenization. ai-memory's MiniLM
implementation uses a 512-token cap, while the HF SentenceTransformers card
documents a 256-wordpiece default. Neither fact qualifies arbitrary long-page
recall. A future change needs an upstream-correct query path and a measured
retrieval/length comparison before re-embedding the real store.

See the [pinned compatibility review](../evidence/artifacts/hf-memory-models-20260921/ai-memory-compatibility.md)
for exact source lines, hashes and boundaries.

## Upstream dashboards and portable evidence

- [Official MTEB model dashboard](https://leaderboard.mteb.org/models/nvidia/Nemotron-3-Embed-1B-BF16): task-specific scores and ranks, languages, context and model metadata. Its live rank depends on the selected benchmark; it is not a local experiment.
- [Official Hugging Face MTEB Space](https://huggingface.co/spaces/mteb/leaderboard): the upstream benchmark application, observed running.
- [Native foundation Grafana](http://127.0.0.1:13000/d/native-foundation-data): the local integration now names the memory model and dimensions; native vLLM series identify the separate serving model. Published model-card limits remain separate from the live endpoint.
- [Qualification receipt](../evidence/receipts/hf-memory-models-20260921.json): native command returns, selected pins, browser observations, source hashes and limitations.
- [Download native returns](http://127.0.0.1:17500/token-savings.html#native): unchanged private outputs; full upstream model cards remain locally retained and linked to their authors.
