# Local models of the new WSL: both slots settled by the preregistered measurement (2026-10-03)

## Decision

The two local-model rows of the definitive manifest, which the rounds left split to a named measurement, are settled by
that measurement:

| Slot | Default | Deciding result |
| --- | --- | --- |
| `local-generation-model` | Swift-1.5-Qwen3.8-27B IQ3_S through Ollama 0.35.0 as `swift-iq3s-s2o-64k` (context 64,000) | first-pass valid tool calls 200 of 200 against 175 of 200 for `gpt-oss:20b`; difference 0.125, 95% paired bootstrap interval 0.065 to 0.19 |
| `embedding-model` | Qwen3-Embedding-0.6B through Ollama 0.35.0 (`qwen3-embedding:0.6b`, Q8_0) as `qwen3-embedding-8k` (context 8,192) | nDCG@10 0.49827 on CQADupstackUnixRetrieval against 0.41394 for EmbeddingGemma; difference 0.084331, interval 0.067738 to 0.100656; Nemotron-3-Embed-1B (0.5014) ties, difference 0.003124, interval -0.012194 to 0.018141, and needs a second model server |

Both models are served by the one model server of the `local-model-server` row. Both results are local integration
checks on one workstation, in a throwaway distribution, with one run per case and arm. They are not an acceptance on
the destination distribution, and they do not establish that either model is the best available.

The manifest carries the results as two settlements in
`evidence/artifacts/new-wsl-definitive-defaults-20261001/settlements.json`, in the form of the model-server settlement:
`settled_by` "preregistered measurement", a label, the basis, the scope, the limits, an overturn condition and two
receipts each (the preregistration's published copy and the part's receipt, by path and sha256). Both rows were added
to the manifest by the convergence decisions (row kind `added`, state and outcome `split`), so the assembler settles
them after those decisions: the state becomes `measurement` with the measurement returned and its receipts, the default
and repository become the measured system's, and the resolution the rounds recorded (outcome `split`, the arms, the
deciding measurement) stays as it was. Neither row becomes definitive. The assembler prints, for the regenerated
manifest:

```
layers 37 | slots 89 {'foundation': 69, 'us-equities': 20} | definitive 31 | installed 58 | {'first_round': 53, 'added': 10, 'consensus': 5, 'judged': 11, 'pinned': 6, 'project_practice': 2, 'no_blind_default_today': 2} | {'definitive': 31, 'resolved': 22, 'measurement': 6, 'split': 5, 'open': 25} | amendments 6 on 6 rows
```

Before the settlements the same line read `installed 56` and `{'definitive': 31, 'resolved': 22, 'measurement': 4,
'split': 7, 'open': 25}`; nothing else changed. These counts describe decisions, not an installation run. The tables
of all rows are generated into [the definitive-defaults record](2026-10-01-new-wsl-definitive-defaults.md).

The install plan's two rows become installable from pinned sources (section "What the install plan does"). As plan rows
they have not run anywhere.

## The deciding measurements and the preregistration

The manifest names the measurements, as the rounds recorded them from the refuting Claude critic
(`evidence/artifacts/new-wsl-final-architecture-20261002/critics/added-critics-result.json`, sha256
`ed444353fae463da52f5f461fb5975eb5d607260d6c219407e77567255b69622`):

- `local-generation-model`: "A fixed tool-call set through the server's three API surfaces with the generation model and
  the embedder both resident on the RTX 4090 at a 64k context: gpt-oss-20b takes the slot if Qwen3.8-27B offloads to
  CPU, evicts the embedder, or has the lower valid tool-call rate."
- `embedding-model`: "Retrieval quality on one fixed public retrieval set through each model's served route, with the
  generation model resident; a model that needs a second model server must beat the best single-server model by an
  interval that excludes zero."

The preregistration fixed the values those sentences leave open before any trial. It was written at
2026-10-02T15:31:48Z, and every amendment was posted with the document's sha256 before the step it names: the hash
chain has 16 entries, the last at 2026-10-03T00:03:17Z, and its last entry, `d161feaa…`, is the sha256 of the final
text. The published copy differs from that text in one span (the throwaway distribution's name, removed); `COPY-NOTES.md`
gives both hashes and the replacement.

Conditions for both parts: Ollama 0.35.0 from the install plan as the one server; an RTX 4090 with 24 GB; every
command, output and exit code kept, a failed call counted as a result. Amendment 1 (18:06:14Z, before any trial) replaced
the free-GPU condition, which would have needed the user's Windows applications closed, by condition N: no WSL process
other than the server under test holds GPU memory, the Windows applications stay as the user has them, and the memory
in use before the first load is recorded. In practice the workstation distribution's two model services were stopped
for each window and started again after it.

## Part A: the generation slot

**As written.** Arms `qwen3.8:27b` (Q4_K_M) and `gpt-oss:20b`. A1, co-residency at 64,000 tokens beside the embedder,
could decide alone; A2, first-pass valid tool calls on 100 cases of the Berkeley Function-Calling Leaderboard's simple
set (shuffle seed 20260927) through the server's surfaces, decided between arms that both passed A1. A difference whose
95% paired bootstrap interval over cases (10,000 resamples, seed 20260927) includes zero is a tie, and a tie goes to the
arm with more free GPU memory with the embedder resident.

**The first result, kept as historical.** A1 (18:06Z to 18:09Z): neither arm met the pass rule; `qwen3.8:27b` was at
92.6% GPU and the server evicted the embedder for both arms. Amendment 2 added A1b, the order of use (the generation
model first, then the embedder, then the long prompt). A1b (18:10Z to 18:16Z): `gpt-oss:20b` was entirely on the GPU
with the embedder resident; `qwen3.8:27b` stayed at 92.6% and failed. By the rule as written `gpt-oss:20b` took the
slot. A1b also showed that with the server-wide context of 64,000 the embedder loaded at its full context and took
5.78 GB; the context belongs to each model, not to the server.

**The extension (amendment 3, 19:18:52Z, before any trial of a new arm).** At about 18:20Z the owner asked, verbatim:
"please only using the latest sota models, with newest advanced releases, you can use the hf key and essential stacks
it related repos of local model optimization etc". The result above was kept as historical, and new arms, selected from
primary sources by the Codex lane, entered under rules hashed before their first trial:

- S1 and S1b: Ternary-Bonsai-2-27B in the packings PTQ1_0 and PQ2_0 (S1b only on S1's failure), on PrismML's
  llama.cpp, a second model server.
- S2: Swift-1.5-Qwen3.8-27B IQ3_S (revision `d74895bb`) on PrismML's llama.cpp, the runtime its card names.
- S2o (declared in amendment 3a): the same Swift file imported into Ollama 0.35.0 with the library `qwen3.8:27b`
  model's Modelfile lines and the Swift file as `FROM`. The publisher documents no Ollama route, so its result is a
  result of this system.
- C: `gpt-oss:20b`, the holder of the historical result, as the control.

Gates and rule: G0, the function gate that settled the model-server slot (the Codex client's MCP tool call through the
server, three scored runs, all must pass), for every arm not on the manifest's server; A1 in the order of use under
condition N; A2 for every arm that passes A1. An arm that fails G0, A1 or A2's floor cannot take the slot; the higher A2
share takes it, with the tie rule above; an arm that needs a second server takes it only if its A2 difference to the
best single-server arm has an interval above zero. Amendment 3a fixed the files, runtimes, requests (reasoning effort
`medium`, 16,384 output tokens) and the embedder's context of 8,192 per model; amendment 3b fixed A2's materials:
Inspect AI 0.3.273 with inspect-evals 0.23.0, task `inspect_evals/bfcl` with `categories=simple_python`, the validity
scorer and the bootstrap program by sha256, and five client tasks for Codex 0.160.0 and Claude Code 2.1.287.

**Results.**

| Arm | G0 | A1 in the order of use | A2 first-pass valid tool calls (chat, responses) |
| --- | --- | --- | --- |
| S1, Bonsai PTQ1_0 on PrismML's server | 0 of 3 | not run | not run |
| S1b, Bonsai PQ2_0 on PrismML's server | 0 of 3 | not run | not run |
| S2, Swift IQ3_S on PrismML's server | 0 of 3 | not run | not run |
| S2o, Swift IQ3_S on Ollama | not applicable (the manifest's server); import gate passed | passed: 14.81 GiB and the embedder 2.66 GiB, each entirely on the GPU | 100 of 100, 100 of 100 |
| C, `gpt-oss:20b` on Ollama | not applicable | passed (A1b): 12.97 GB (12,968,494,366 bytes, 12.08 GiB; the preregistration's text says 12.97 GiB) entirely on the GPU, the embedder resident | 87 of 100, 88 of 100 |

- The three PrismML arms failed G0 for the reason that settled the model-server slot: the server's log carries
  `unsupported Responses tool type 'namespace' skipped` and no call of the time server's tool is recorded. That is a
  result about that server's Responses layer, not about the models' tool calling elsewhere.
- Decision statistic: shares 1.000 for S2o and 0.875 for C over 200 case-surface pairs each; difference 0.125; interval
  0.065 to 0.19. Not a tie. By the rule, **S2o takes the slot**, served as the derived model `swift-iq3s-s2o-64k`, which
  carries the context of 64,000 as its own parameter.
- C's 25 invalid cases: 18 with arguments outside a schema's allowed values (for example `pop` where the schema allows
  `Pop`) and 7 without a tool call, judged by the frozen definition.
- Recorded, not deciding: the package's own score (S2o 97 and 95 of 100, C 83 and 83); the client tasks (ten of ten
  file checks for each arm, Codex and Claude Code); seconds for the 100 cases (S2o 292 and 303, C 100 and 139); output
  tokens per second on single long prompts not run as a speed comparison (S2o 43.1, C 108.9).
- The Anthropic-style messages surface was not evaluated through the package: Inspect AI 0.3.273's provider cannot
  read this thinking model's answer. Claude Code exercised that surface in the client tasks, which both arms passed.

## Part B: the embedding slot

**As written.** Arms `qwen3-embedding:0.6b` and `embeddinggemma` through the one server, and Nemotron-3-Embed-1B through
a second server; the MTEB task CQADupstackUnixRetrieval, test split; nDCG@10 with a paired bootstrap over queries
(10,000 resamples, seed 20260927); the generation model that took Part A resident throughout. Between the single-server
arms the higher nDCG@10 takes the slot, a tie going to the smaller resident memory; a second-server arm takes it only
with an interval above zero against that winner.

**Amendment 4 (22:48:48Z, before any download of an arm's weights)** fixed MTEB 2.22.1, the dataset revision
`6c6430d3a6d36f8d2a829195bc5dc94d7e063e53` (47,382 documents, 1,072 queries, 1,693 judgements), and the arms: E1
`qwen3-embedding:0.6b` (library manifest `ac6da0df…`) as `qwen3-embedding-8k`; E2 `embeddinggemma`; E3
Nemotron-3-Embed-1B and E4 WeMM-Embedding-2B (from the other lane's proposal) at MTEB's registered revisions, in the
evaluation process. Gate F (fit beside the generation model) applied to E3 and E4, gate C (the per-query mean equals
MTEB's score) to every arm. The reranking condition the other lane proposed was not run: no installed retrieval owner
can call an external reranker, and zerank-2 (7.49 GiB of weights) cannot be resident beside the generation model.
**Amendment 4a (23:12:42Z, before any load)** corrected what an independent read of the scripts found: the prompts of E1
and E2 (MTEB's wrapper would have sent none), gate C's tolerance (MTEB rounds to five decimals), gate F on the CPU and
its batch size, failures without a record, unloading and residency checks; and it fixed gate F's outcomes (exit 1 does
not fit, exit 2 another error, which removes no arm).

**Results.**

| Arm | Window | Gate F | nDCG@10 | Gate C |
| --- | --- | --- | --- | --- |
| E1 `qwen3-embedding-8k` on Ollama | pb1 | not applicable | 0.49827 | passes |
| E2 `embeddinggemma` on Ollama | pb1 | not applicable | 0.41394 | passes |
| E3 Nemotron-3-Embed-1B, in process | pb2 | exit 0 (exit 2 in pb1: a setup error, deviation 4) | 0.5014 | passes |
| E4 WeMM-Embedding-2B, in process | pb2 | exit 0, then out of memory in the full run after 47.5 s | none | none |

- E1 minus E2: 0.084331, interval 0.067738 to 0.100656, not a tie: E1 is the single-server winner.
- E3 minus E1: 0.003124, interval -0.012194 to 0.018141, which includes zero: E3 does not take the slot.
- E3 minus E2, recorded and not deciding: 0.087455, interval 0.072733 to 0.102348.
- E4 is out: by amendment 4a an arm that passes F and runs out of memory in the full run does not fit beside the
  generation model.
- By the rule, **E1 takes the slot**, served as the derived model `qwen3-embedding-8k`, which carries `num_ctx` 8192 as
  its own parameter. Both local-model slots are served by the one model server.
- Recorded, not deciding: evaluation time E1 1,166 s, E2 771 s, E3 460 s (in process, not comparable with the Ollama
  arms); resident sizes E1 2,857,191,341 bytes, E2 681,417,113 bytes and the generation model 15,897,985,023 bytes,
  each entirely on the GPU in pb1.

## Deviations and recorded defects

The preregistration records each with its time, before the step that followed. None changed a case, a limit, the
metric or a rule, and none was decided on an outcome.

1. **The void first G0 window (19:47:42Z).** Condition N was not met: the measurement server still held `gpt-oss:20b`
   from A1b (11.92 GiB). The window was stopped on the memory figure alone; the attempt is void because its
   precondition failed, its state folder is kept under its own name, and S1's G0 ran again from a fresh state. Every
   later window checked the precondition before any load.
2. **The Codex client's model name.** In the unscored pilot Codex's local-provider setup did not find
   `swift-iq3s-s2o-64k` without its tag and tried to pull it; the runner now passes the name with its tag to Codex only.
   This is one of the two repairs the pilot was allowed to make.
3. **A reused label.** The window gave both arms one label, the runner refused C's client runs, and the window script
   wrote the refusals over the workstation-side copies of S2o's records; the records inside the distribution were
   intact. C's tasks ran once under their own label.
4. **Gate F setup errors in pb1.** E3 stopped on a missing C compiler for triton and E4 on a missing torchvision, each
   exit 2, which by amendment 4a is not a fit result. The window script printed "out" for both, contrary to that rule;
   the records count. Exactly the two missing pieces were added and both arms ran in pb2.

Also recorded: a printed summary's count of "HTTP 500" lines at G0 matched other numbers in the debug log, so no HTTP
500 is established; E4's first error text was lost, because the script's memory query raised the same sticky CUDA error
and the outer handler replaced the text (the outcome is not in doubt: only the evaluation's handler sets
`out_of_memory`); and in pb2 the card's memory in use fell between steps (19,856 MiB after the generation model loaded,
1,906 MiB at the end) while the server kept listing the generation model entirely on the GPU. Gate F reads that
listing, so "E3 passes F" means it passed the frozen criterion, not that co-residency is shown. In pb1 the readings
matched the resident models, so E1's co-residency with the generation model is supported by both readings.

## The other model family's read

The Codex lane read the preregistration and the result notes of both parts independently and read-only (its comment
names each file by bytes and sha256), and posted its result on pull request 608 (comment 5964331790,
2026-10-03T01:54:48Z). It found the documented frozen-rule application consistent for both slots,
said the owner may prepare the two-slot evidence pull request, and checked the preregistration's bytes, its hash chain
and MTEB 2.22.1's metric and wrapper source. It asked for one evidence amendment before an independent acceptance of
the native results: an artifact map with locators, hashes, times and exit lines of the retained records. It asked that
the void window, the tag correction, the label refusals, the failed arms and setups and E4's lost error text be kept; it
stated that the pb2 readings and a full-GPU server listing do not establish physical co-residency or a verified paging
explanation; and it stated that neither selection establishes global SOTA or the destination's installation and GPU
acceptance.

The map is posted and private (`wsl-architecture-design-local-models-artifact-map-20261003.md`, 32,231 bytes, sha256
`bd269c02545d39a23bedaf1893de254b572065108d2f8a6581942b8f15d0237f`, 175 artifacts). The Codex lane's binding read of the
map (`CODEX-LOCAL-MODEL-MAP-BINDING-READ-20261003.md` in the private coordination folder, 2,387 bytes, sha256
`8e14fc721add5805ffa11b44e59de0fbe863aa9e5d964a8048ef69d4f0760dc5`, written at 2026-10-03T03:18Z) states that it checked
all 175 listed files against their declared sizes and sha256 (98,332,676 bytes; none missing, none different) and that
it accepts the map's local file bindings only: record timestamps, process exits, scorer correctness, the copied
collection's combined digest and remote-side identity are separate claims that matching hashes do not authenticate. It
also states that a verdict on the exact head of the evidence pull request is still required. That verdict, and the other
family's acceptance of the native results, are not recorded here.

The published folder's `files.json` lists the 231 files the measurement folder held when it was listed, by sha256. A
copy-out of the throwaway's measurement directories (55,649 files) was added to the private folder afterwards, at about
2026-10-03T05:37Z; `files.json` lists it by the sha256 of its checksum list, and its files were not checked against that
list for this publication.

## What the install plan does

`evidence/artifacts/new-wsl-install-plan-20261002/` (README, section "The two local-model rows"):

- `local-generation-model` downloads the IQ3_S file at the pinned Hugging Face revision and keeps it only with its
  sha256 `1333c6ea…a786` (11,771,546,912 bytes), places the repository's Modelfiles beside it and creates
  `swift-iq3s-s2o` and `swift-iq3s-s2o-64k`. The Swift Modelfile is the measured one with its `FROM` line written
  relative to the Modelfile. The measured file is in the copy-out added to the private folder after its listing (11,758
  bytes, the recorded sha256 `8911245e…`), and after its `FROM` line it is byte-identical to the plan's copy;
  `evidence/artifacts/new-wsl-local-models-20261002/reconstruct_s2o_modelfile.py` rebuilds it independently from the
  library model's blobs and reproduces that sha256. The derived Modelfiles of both rows are byte-identical to the ones
  the measurement wrote.
- `embedding-model` pulls `qwen3-embedding:0.6b`, stops unless the server lists the pinned library manifest digest, and
  creates `qwen3-embedding-8k`.
- The preregistration said the winners would be pulled with `ollama pull`. That holds for the embedder. The generation
  winner is a file from its publisher's repository imported with the library model's Modelfile lines, not a library
  model, so the plan downloads that file pinned by revision and sha256 and creates the measured system from the
  measured Modelfile.
- No server-wide context is set anywhere in the plan; each derived model carries its own.
- The measurement's server, as `steps/M12-reprepare.sh` (private) started it after deviation 1 and before S2o's first
  load, also ran with `OLLAMA_NUM_PARALLEL=1` and `OLLAMA_KEEP_ALIVE=-1`; no later step script starts it again. The plan
  sets neither. Ollama v0.35.0's default for the first is 1, the measured value, so each model is served with one
  request slot as measured; its default keep-alive is five minutes, so on the plan's server an idle model leaves the GPU
  after five minutes, where the measured server never unloaded an idle model. Keeping both resident is a question for
  the lifecycle design, with GPU ownership below.
- The `local-model-server` row's `after_sign_in` smoke check ran upstream's example `ollama run embeddinggemma`, which
  would pull EmbeddingGemma, the embedding arm that lost. It is now one `/api/embed` call to `qwen3-embedding-8k`, which
  downloads nothing.
- Both rows create their models through the running model server, which the plan does not start, so the default run
  skips them and `--only` installs each. Their acceptance reads files after the install (the placed Modelfiles, the
  library manifest's digest, the created models' layers) and, once the server answers, shows each model's own context
  and makes one short generation or one embedding call.
- **GPU ownership is a limitation for the lifecycle design.** One RTX 4090 serves the workstation distribution's model
  services and the destination's model server. The measured co-residency held under condition N, with the workstation's
  two model services stopped. Which distribution's server holds the card, and when, is not decided here, and the plan
  starts no service.

## What is not established

- **The destination's acceptance.** Neither row has been installed or checked on the destination distribution, and no
  command of either row has run as a plan row anywhere. GPU residency there, beside whatever else then holds the card,
  is not measured.
- **Physical co-residency in pb2.** Gate F read the server's listing while the card's used memory fell; E3's pass is a
  pass of the frozen criterion. E1's co-residency rests on pb1, where both readings agree.
- **One host, one task each.** One workstation, one throwaway distribution, one run per case and arm. Generation: 100
  simple public cases through two surfaces, plus five client tasks per client that did not decide. Embedding: one
  English technical retrieval task. The critic's own measurement text named more than the manifest's deciding
  measurements kept: for the embedder the retrieval tasks of MTEB (eng, v2) and MTEB (Code, v1) and a judged set of
  this host's session text, at 768 dimensions and at native size; for the generator Codex request shapes including
  `apply_patch` through the responses surface and Claude Code's shapes through the messages surface. Those were not
  measured.
- Coding quality, long tasks, throughput under concurrent requests and behaviour above 64,000 tokens; multilingual
  retrieval, other domains and longer documents; the reranking condition.
- Co-residency on a busier desktop: before the loads of these windows the Windows applications held from about 2,200
  MiB (the A2 runs) to 4,407 MiB (pb1), and earlier on 2026-10-02 up to about 5,900 MiB, at which the measured load
  would leave under one GB free.
- That the measured difference belongs to the weights alone: each arm is a system of a file, a template and a runtime,
  and the Ollama arms are GGUF conversions.
- Global SOTA, which neither selection establishes.

## Where the change lands

- `evidence/artifacts/new-wsl-local-models-20261002/`: the preregistration's copy, its hash chain and copy notes, the
  two receipts, the per-case and per-query records from which both statistics reproduce, the frozen scorers, runners
  and steps, the Modelfile reconstruction and `files.json`.
- `evidence/artifacts/new-wsl-definitive-defaults-20261001/`: the two settlements; the assembler settles a split row
  that the convergence decisions added; the manifest, the tables of the definitive-defaults record and the handbook are
  regenerated.
- `.gitignore`: two exceptions to its `*.jsonl` rule, so that the per-case and per-query records are committed.
- `evidence/artifacts/new-wsl-install-plan-20261002/`: the two rows, their Modelfiles, the `local-model-server` row's
  `after_sign_in` check, both scripts, the checker and the README, SOURCES and VALIDATION sections;
  `tests/test_new_wsl_definitive_defaults.py` (class `LocalModelAcceptance`).
- `manifests/evidence.json`: the two receipts, kind `native_model_e2e`.

## Sources

| File | sha256 |
| --- | --- |
| `evidence/artifacts/new-wsl-local-models-20261002/PREREGISTRATION-local-models.md` (published copy) | `454f879d03d61fa5a8e9f0d877e62cd94878abcd32f8f09b16ac9514492c3a0b` |
| The preregistration's final text (private; last entry of the chain) | `d161feaacd6b3082b3adf37e80a368b58bd6f68205efd399102b8d84d0d0f78b` |
| `evidence/artifacts/new-wsl-local-models-20261002/PREREGISTRATION-local-models.sha256` | `7645e3a1bd9d94c478849ae20b07dc3f6b6f7a778ec0dfe74715b6123b71021a` |
| `evidence/artifacts/new-wsl-local-models-20261002/part-a-receipt.json` | `55ac6ff05f4437dffb2623117c71fb8d6f786d71e63a44b46973b145b1d29577` |
| `evidence/artifacts/new-wsl-local-models-20261002/part-b-receipt.json` | `6f5dfbf83c5116e38b42d38ddd5fdbb1a27cf23b5ef7e8ac12d4071c9173a541` |
| `evidence/artifacts/new-wsl-local-models-20261002/files.json` | `4e77359503133255d0dc30f44e6c577839bfa6124d1146f6ebb0ddff423f1893` |
| `evidence/artifacts/new-wsl-final-architecture-20261002/critics/added-critics-result.json` | `ed444353fae463da52f5f461fb5975eb5d607260d6c219407e77567255b69622` |
| The artifact map (private) | `bd269c02545d39a23bedaf1893de254b572065108d2f8a6581942b8f15d0237f` |
| The Codex lane's binding read of the map (private) | `8e14fc721add5805ffa11b44e59de0fbe863aa9e5d964a8048ef69d4f0760dc5` |

- The other family's read: https://github.com/seathatflowsinourveins/native-agent-stack/pull/608#issuecomment-5964331790
- Upstream versions as run: Ollama 0.35.0 (tag on `cc4069396f3ad2c370c53eed2e4a42ac13adab84`), Inspect AI 0.3.273,
  inspect-evals 0.23.0 (`bd59dd3b48974ad2e91219a6ceed41011e201163`), MTEB 2.22.1 (`79857d39`), Codex 0.160.0, Claude
  Code 2.1.287.
- Reproduction, on the published records alone: the evidence folder's README gives the four commands; on 2026-10-03
  each printed the line recorded in `part-a/bootstrap.txt` and `part-b/bootstrap.txt`. That re-derives the statistics;
  it does not re-measure anything.

## Overturn

- **Generation.** A newer local generation model or runtime that passes the function gate, fits entirely on the GPU
  beside the embedder at 64,000 tokens and has a higher first-pass valid tool-call share on the same cases with an
  interval above zero; or the destination's acceptance failing for this system (the model not created from the pinned
  file, or not answering through the server).
- **Embedding.** A single-server embedding model with a higher nDCG@10 on the same task whose difference has an interval
  above zero; a second-server model that beats this one by an interval above zero; a measured gain of an external
  reranker once a retrieval owner that can call one is installed; or the destination's acceptance failing for this
  system.
- A measurement of what the critic named beyond the deciding measurements (code retrieval, session text, the clients'
  own request shapes) that reverses either order.
