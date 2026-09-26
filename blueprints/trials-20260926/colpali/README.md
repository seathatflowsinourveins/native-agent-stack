# ColPali / ViDoRe trial (2026-09-26)

**Measured result:** `vidore/colpali-v1.3`, run through the unchanged
`vidore-benchmark` 5.0.0 `evaluate-retriever` CLI on CPU, scored **nDCG@5
0.89682** (recall@3 1.0) on a 12-image slice of `vidore/tabfquad_test_subsampled`,
against **0.19678** (recall@3 0.25) for the CLI's built-in random-embedding
control on the same slice; a self-contained CPU reproduction gave the same
numbers. The model the trial brief suggested, `vidore/colqwen2.5-v0.2`, was
**not evaluated**: the 5.0.0 CLI registers no ColQwen2.5 retriever, the Python API
that 5.0.0 documents for other retrievers was not tried, and the model's processor
at the pinned Hub revision does not load within colpali-engine 0.3.13's
transformers range ([finding 2](#findings)). The layer decision is not made here
(see [Verdict](#verdict)).

Machine-readable record: [`results-20260926.json`](results-20260926.json).
Every retained file, with sha256, evidence class and sanitization:
[`retained-outputs.json`](retained-outputs.json). Pinned source lines behind the
findings: [`source-review.json`](source-review.json). Batch rules:
[`../README.md`](../README.md).

## What it is

[ColPali](https://github.com/illuin-tech/colpali) (`colpali-engine`, MIT) is a
family of late-interaction visual document retrievers: a vision-language model
embeds each image patch and each query token, and retrieval scores are ColBERT
MaxSim, so page images are indexed without OCR.
[ViDoRe](https://github.com/illuin-tech/vidore-benchmark) (`vidore-benchmark`,
MIT) is the paired evaluation package. Upstream now marks `colpali-engine`
deprecated for new projects in favour of Sentence Transformers v6
`MultiVectorEncoder`, and `vidore-benchmark`'s main branch moved single-model
evaluation to MTEB (`source-review.json#colpali-deprecation`, `#vidore-main-mteb`).

## Pins

| Pin | Value | Verified by |
| --- | --- | --- |
| `colpali-engine` (installed) | `0.3.13` = tag `v0.3.13` = `174055b00d4a36f672c6f915f2bdd0002e4fc9ee`, wheel `4f6225a4…8002` | tag clone `git rev-parse`; PyPI-reported and downloaded sha256 |
| `colpali-engine` (PyPI latest at the trial, not co-installable) | `0.3.18`, wheel `9f04fa89…9d4` | same |
| `vidore-benchmark` | `5.0.0` = tag `v5.0.0` = `d167f9ce6be840c5d887aa5cb1c01d2060485c93`, wheel `ad2b2141…a7b6`, sdist `cb3d1a68…b80c` | same |
| Hub | `vidore/colpali-v1.3` `b5c6dd62…0a11`; `vidore/colpaligemma-3b-pt-448-base` `30ab955d…5e5a`; dataset `vidore/tabfquad_test_subsampled` `16c8e633…580f` | Hub revision API |
| Environment | [`reproduction/requirements-lock.txt`](reproduction/requirements-lock.txt) (torch 2.8.0, transformers 4.53.1, sentence-transformers 3.4.1, datasets 5.0.1) | the reproduction checks the installed set equals it |

Pin checks: [`../provenance/run-20260926T045856Z/verify-pins.log`](../provenance/run-20260926T045856Z/verify-pins.log).
The first pass's candidate row carried `174055b0…` without saying what it was;
it is the `v0.3.13` tag commit of `illuin-tech/colpali`.

## Results

| Check | Evidence class | Exit | Result | Retained |
| --- | --- | --- | --- | --- |
| `uv pip install colpali-engine==0.3.18 vidore-benchmark==5.0.0` | upstream native operation | 1 | unsatisfiable: 0.3.18 needs `transformers>=5.3.0`; vidore-benchmark 5.0.0 needs `sentence-transformers<4`, which needs `transformers<5` | [log](native-outputs/install-colpali-engine-0.3.18-with-vidore-benchmark-5.0.0-conflict.log) |
| `uv pip install "vidore-benchmark[colpali-engine]==5.0.0"` (the documented extras), then `transformers==4.53.1` | upstream native operation | 0 | `colpali-engine` 0.3.13, transformers 4.57.6 → 4.53.1 | [install](native-outputs/install-vidore-benchmark-5.0.0-colpali-engine-extra.log), [pin](native-outputs/install-transformers-4.53.1.log) |
| Unreported first-pass install in a separate venv | upstream native operation | not retained | `colpali-engine` 0.3.18 + mteb 2.21.8 + sentence-transformers 6.1.0 + transformers 5.17.0 installed together; nothing evaluated there | [log](native-outputs/install-mteb-2.21.8-colpali-engine-0.3.18.log) |
| `--model-class colqwen2 --model-name vidore/colqwen2-v1.0`, six attempts | upstream native operation | 1 | 1: wrong venv (ImportError); 2-4: offline-mode setup errors; **5 and 6: `TypeError: expected str, bytes or os.PathLike object, not NoneType` in `ColQwen2Processor.from_pretrained` at transformers 4.57.6 and again at 4.53.1** (cause: finding 2) | [attempts](native-outputs/) |
| Processor-load probe ([source](local-integration/colqwen_processor_probe.py)), CPU, fresh private `HF_HOME`, the first pass's venv (transformers 4.53.1) | local integration | 0 | all five expectations written before the run held: `ColQwen2Processor` (colqwen2-v1.0, main) and `ColQwen2_5_Processor` (colqwen2.5-v0.2 at the pinned `dcbe8d9c`) raise the attempts' `TypeError`; both load at the last revision before the Hub added `additional_chat_templates/` (`83a0134c`, `6f6fcdfd`), with `process_images`, `process_queries` and `score` | [output](native-outputs/colqwen-processor-probe-20260926T0634Z.ndjson), [Hub files](native-outputs/hf-chat-template-files.txt) |
| colpali-v1.3, full 280-row split, CPU | upstream native operation | not retained | queries done in 5 min 20 s; 6 of 70 image batches done, at 162-243 s each; the log then stops with no exit line and no metrics (the first pass reported a 1700 s timeout, which neither the script nor the log shows) | [log](native-outputs/eval-colpali-v1.3-full280-cpu-interrupted.log) |
| Random control, full split | upstream native operation | 0 | nDCG@5 0.0334 | [log](native-outputs/eval-dummy-full280-cpu.log) |
| **colpali-v1.3 and random control, 12-row slice, self-contained CPU reproduction** ([script](reproduction/reproduce-cpu.sh)) | upstream native operation + local integration check | 0 | colpali: **nDCG@5 0.89682**, nDCG@1 0.75, recall@3 1.0, device logged `cpu`, 529 s wall, 9315 CPU-s (8905 user + 410 system), peak RSS 42.7 GB (GNU time: 41,712,648 KiB). Control: **nDCG@5 0.19678**, recall@3 0.25, 7 s | [run-20260926T0412Z](reproduction/run-20260926T0412Z/) |
| Same slice, first pass, CPU | upstream native operation | 0 | the same metrics; 14 min 3 s wall under sibling-trial load (206, 226 and 266 s per image batch) | [colpali](native-outputs/eval-colpali-v1.3-slice12-cpu-original.log), [control](native-outputs/eval-dummy-slice12-cpu-original.log) |
| Same slice, first pass's recorder, no device pin | upstream native operation | 0 | the same rank metrics in 216 s, 119.1 s and 105.0 s; device not logged, GPU indicated (finding 5) | [dry run](native-outputs/recorder-dryrun-slice12-unpinned-device.log) |
| Weight licences | registry observation | 0 | see [Licences](#licences) | [Hub fields](native-outputs/hf-license-chain.txt) |

The reproduction rebuilds the slice from the pinned dataset revision with
[`build_slice.py`](reproduction/build_slice.py) and checks it is byte-identical
to the first pass's input ([`slice-expected.json`](reproduction/slice-expected.json));
the slice builder and the shell steps are local integration glue, the retrieval
and metrics are the CLI's own. The random control uses `torch.randn` embeddings
under the CLI's fixed `set_seed(42)`, so its metrics are identical in every run
(`#dummy-retriever`, `#cli-fixed-seed`).

## Findings

1. **Working retrieval on a real ViDoRe slice.** colpali-v1.3 ranks the correct
   page first for 9 of 12 queries (nDCG@1 0.75) and within the top 3 for all 12,
   against a control at nDCG@5 0.19678. The 12-row slice is too small to compare
   with ViDoRe aggregates such as the 84.8 the upstream README lists for this
   model.
2. **colqwen2.5-v0.2 was not evaluated; the 5.0.0 CLI cannot select it, and its
   processor does not load at the pinned revision.**
   - *CLI registry:* no `--model-class` retriever exists for ColQwen2.5. The
     `colqwen2` retriever loads `ColQwen2`/`ColQwen2Processor`, while
     colqwen2.5-v0.2's base (`vidore/colqwen2.5-base`) declares
     `architectures: ["ColQwen2_5"]`, `model_type: "qwen2_5_vl"`
     (`#colqwen2-retriever-classes`, `#retriever-modules`; Hub fields in
     [`verify-pins.log`](../provenance/run-20260926T045856Z/verify-pins.log)).
   - *Python API, not tried:* vidore-benchmark 5.0.0 documents
     `VisionRetriever(model, processor)` wrapped in `ViDoReEvaluatorQA` for
     retrievers outside the CLI's list; it needs only a processor with
     `process_images`, `process_queries` and `score` (`#vidore-python-api`,
     `#vision-retriever-processor-methods`). colpali-engine 0.3.13 exports
     `ColQwen2_5` and `ColQwen2_5_Processor`, a `BaseVisualRetrieverProcessor`
     subclass (`#colpali-engine-classes`, `#colqwen2_5-processor-class`).
   - *Processor loading:* the six `colqwen2-v1.0` attempts failed on a
     chat-template file, not on the architecture. On 2026-08-17 both
     `vidore/colqwen2-v1.0` and `vidore/colqwen2.5-v0.2` gained
     `additional_chat_templates/sentence_transformers.jinja`
     ([Hub files](native-outputs/hf-chat-template-files.txt)). transformers
     4.53.1 and 4.57.6, the two ends of colpali-engine 0.3.13's range (versions
     between them not checked), list that file with its `.jinja` suffix, request
     `additional_chat_templates/sentence_transformers.jinja.jinja`, get `None`
     for the missing file and pass it to `open()`, which raises the attempts'
     `TypeError` (`#transformers-4.53.1-*`, `#transformers-4.57.6-*`).
     transformers 5.0.0 strips the suffix
     (`#transformers-5.0.0-processor-strips-suffix`), but colpali-engine 0.3.13
     requires transformers `<4.58.0` (`#colpali-engine-deps`). The processor
     probe (local integration, results table) confirmed this for both models,
     including colqwen2.5-v0.2 at the pinned `dcbe8d9c`, and showed that both
     processors load at the last revision without the template. The
     colqwen2.5-v0.2 weights were never downloaded.
3. **Version conflict with the latest release.** `colpali-engine` 0.3.18 does not
   co-install with `vidore-benchmark` 5.0.0; it does install with mteb 2.21.8 and
   sentence-transformers 6.1.0 (not evaluated).
4. **CPU cost.** 149 s per batch of 4 page images in the reproduction (load
   average 22-28). Under heavier contention the first pass took 206-266 s per
   batch on the slice and 162-243 s on the full split. These are per-batch times
   from the logs' elapsed stamps; the port had quoted tqdm's `s/it` column,
   which is a smoothed average. The 12-row slice took 529 s wall and 9315.11
   CPU-seconds (8905.32 user plus 409.79 system), with a peak RSS of 42.7 GB
   (39.8 GiB): GNU time reports 41,712,648 in KiB. The first pass's "peak RSS about 8 GB" is not supported by
   `/usr/bin/time -v`.
5. **The CLI uses the GPU by default.** `vidore-benchmark` 5.0.0 resolves device
   `auto` to `cuda:0` whenever CUDA is visible (`#device-auto`,
   `#colpali-retriever-device`). The first pass's recorder ran without
   `CUDA_VISIBLE_DEVICES=''`; its document forward passes took about 0.5 s per
   batch of 4 images against 149 s on CPU. Its receipts nevertheless claimed an
   843.3 s CPU run. This reconciles the 843 s / 105-119 s gap the program review
   found: the 843 s run was CPU under load, the short ones were GPU-indicated.

## Licences

Code: MIT for both packages. Weights (Hub cards, retained): `vidore/colpali-v1.3`
says `mit` but is an adapter on `vidore/colpaligemma-3b-pt-448-base` (`gemma`),
itself from `google/paligemma-3b-pt-448` (`gemma`, gated). `vidore/colqwen2.5-v0.2`
says `mit`, on `vidore/colqwen2.5-base` (`apache-2.0`), on
`Qwen/Qwen2.5-VL-3B-Instruct` (`qwen-research`). The colpali README table lists
colpali-v1.3 as Gemma and colqwen2.5-v0.2 as Apache 2.0 (`#readme-model-table`).

## Blocked and not evaluated

- colqwen2.5-v0.2: not selectable through the vidore-benchmark 5.0.0 CLI;
  the documented 5.0.0 Python API path was not tried; its processor does not
  load at the pinned revision within colpali-engine 0.3.13's transformers range
  (finding 2).
- The full 280-row split: the CLI embeds each query row's image, so 280 images
  in 70 batches. At the observed 149-243 s per batch that is about 2.9 to 4.7
  hours of image embedding plus about 5 minutes of queries. The trial ran on CPU
  by intent; three first-pass runs without a device pin were GPU-indicated
  (finding 5).
- Not evaluated: any intentional GPU run, the vidore-benchmark 5.0.0 Python API,
  the MTEB and Sentence Transformers v6 paths upstream now recommends, and the
  other ViDoRe datasets.

## Withdrawn receipts

Four first-pass receipts are kept byte-for-byte in
[`withdrawn-host-receipts/`](withdrawn-host-receipts/). `scripts/host_receipts.py
validate` rejects `colpali-engine` and `vidore-benchmark` as component ids
([`../README.md`](../README.md#why-there-are-no-host-receipts)). The two use
receipts also claimed an 843.3 s CPU run while their recorded commands took
119.1 s and 105.0 s with no device pin, and the two install receipts were
self-written `python -c` checks.

## Host state

The first pass's unpinned-device runs downloaded `vidore/colpali-v1.3` (113 MB)
and `vidore/colpaligemma-3b-pt-448-base` (5.85 GB) into the host's default Hugging
Face cache, creating `~/.cache/huggingface/hub`, and left an hf_xet log. Building
the local slice created `~/.cache/huggingface/datasets`, and importing mteb 2.21.8
created the empty `~/.cache/mteb`. All of these are still on the host, because
they lie outside the session scratch directory. The first pass's `trial-colpali`
scratch tree (31 GB) was deleted by the polish pass, and the
`/tmp/nas-colpali-trial` alias symlink was removed. Sizes, evidence and removal
commands: [`../README.md`](../README.md#host-state).

## Verdict

- **Measured:** colpali-v1.3 through the unchanged vidore-benchmark 5.0.0 CLI on
  CPU: nDCG@5 0.89682 and recall@3 1.0 on a 12-image TabFQuAD slice against
  0.19678 and 0.25 for the random control; reproduced self-contained.
- **Blockers:** colqwen2.5-v0.2 is not selectable through the vidore-benchmark
  5.0.0 CLI, and its processor at the pinned Hub revision does not load within
  colpali-engine 0.3.13's transformers range. The documented 5.0.0 Python API
  path is untried. The PyPI-latest colpali-engine does not co-install with
  vidore-benchmark 5.0.0, and CPU throughput made the full split impractical.
- **Facts:** colpali-engine is deprecated upstream in favour of Sentence
  Transformers v6 `MultiVectorEncoder`; vidore-benchmark's main branch moved
  evaluation to MTEB; code is MIT and the weight licences follow the base models.
- **Layer decision:** not made here. The foundation document-retrieval layer is
  re-recorded by its own verdict wave
  (`tools/sota-convergence/record_verdicts.py`).
- **Re-trial trigger:** colqwen2.5-v0.2 on the same slice and control through
  two routes. First, the vidore-benchmark 5.0.0 Python API (`VisionRetriever`
  plus `ViDoReEvaluatorQA` with `ColQwen2_5`), either at the pre-template
  revision `6f6fcdfd` or with a colpali-engine and transformers pair that loads
  the current revision. Second, the upstream-recommended path (Sentence
  Transformers v6 `MultiVectorEncoder` or MTEB's ViDoRe tasks). Then a full split
  in a GPU window the host schedule allows.
