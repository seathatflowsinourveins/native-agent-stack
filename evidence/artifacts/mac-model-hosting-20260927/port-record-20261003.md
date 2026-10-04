# Port record: the Mac session's 2026-09-27 model-hosting observations

Port date: 2026-10-03. Source: [PR #410](https://github.com/seathatflowsinourveins/native-agent-stack/pull/410)
at `14b5c52145d9cc42d4c9da36df53ac994009856a`. Prepared on main at
`cac8700ba914950266272347468bff7ad630a4bf`; [PR #670](https://github.com/seathatflowsinourveins/native-agent-stack/pull/670) records the merge base. Lane: `lane:foundation`.

These artifacts preserve the Mac coordinator session's descriptive observations.
They establish no host acceptance or qualification, change no host role or pin,
and transfer no acceptance to the workstation or the new WSL target. No new Mac
execution was performed for the port. The north-star action served is retaining
the historical model-hosting comparison for foundation R&D and a future Mac
qualification with its own controls and reproducible inputs.

## Provenance

The source branch is `claude/mac-model-hosting-20260927`; its head and
`refs/pull/410/head` are `14b5c52145d9cc42d4c9da36df53ac994009856a`.
The four source commits are:

- [`2d33dbd5b`](https://github.com/seathatflowsinourveins/native-agent-stack/commit/2d33dbd5bae0b82a7aca821f9cd8dfbb6deec966),
  `2d33dbd5bae0b82a7aca821f9cd8dfbb6deec966`;
- [`b16b84b82`](https://github.com/seathatflowsinourveins/native-agent-stack/commit/b16b84b821f75a8c900557b763a2cdbef62e8f4e),
  `b16b84b821f75a8c900557b763a2cdbef62e8f4e`;
- [`867fd4bf6`](https://github.com/seathatflowsinourveins/native-agent-stack/commit/867fd4bf6e0662c1f5890ff1d8c0b9ad7d6a8f04),
  `867fd4bf6e0662c1f5890ff1d8c0b9ad7d6a8f04`;
- [`14b5c5214`](https://github.com/seathatflowsinourveins/native-agent-stack/commit/14b5c52145d9cc42d4c9da36df53ac994009856a),
  `14b5c52145d9cc42d4c9da36df53ac994009856a`.

The annotated tag `receipt-revision/b16b84b8` peels to
`b16b84b821f75a8c900557b763a2cdbef62e8f4e`. The branch, pull-request ref and tag
are preserved. The review is
[comment 5857332260](https://github.com/seathatflowsinourveins/native-agent-stack/pull/410#issuecomment-5857332260);
the parked note is
[comment 5883318917](https://github.com/seathatflowsinourveins/native-agent-stack/pull/410#issuecomment-5883318917).
The later
[custody notice](https://github.com/seathatflowsinourveins/native-agent-stack/pull/410#issuecomment-5967134391)
sets the descriptive port and preserves #379 for a Mac session.

## Disposition of all 15 files from #410

Paths in the first nine rows are relative to this directory. “Ported with
corrections” for the two existing documents means only the assigned passages,
not replacement of their current-main content. The source registry is not
ported: current-main registration is regenerated separately.

| Source file | Disposition |
| --- | --- |
| `README.md` | Ported with corrections, each marked “Corrected 2026-10-03 (port of #410)” |
| `capacity.json` | Ported byte-identical |
| `coresidency.json` | Ported byte-identical |
| `embed-acceptance.json` | Ported byte-identical |
| `gate.json` | Ported byte-identical |
| `li26-mac-descriptive.json` | Ported byte-identical |
| `li26-window-samples.json` | Ported byte-identical |
| `li26_mac_descriptive.py` | Ported byte-identical; not executed against private run state by this port |
| `swap-event.json` | Ported byte-identical |
| `adoption/platforms/macos-arm64.md` | Ported with corrections to two dated passages; the qualification sentence is preserved |
| `docs/harness-defaults.md` | Ported with corrections: verified append to the existing unpublished-revision row only |
| [`adoption/host-roles.json` at `14b5c521`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/14b5c52145d9cc42d4c9da36df53ac994009856a/adoption/host-roles.json) | Not ported |
| [`docs/decisions/2026-09-27-mac-native-model-hosting.md` at `14b5c521`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/14b5c52145d9cc42d4c9da36df53ac994009856a/docs/decisions/2026-09-27-mac-native-model-hosting.md) | Not ported; unique historical facts are attributed below |
| [`evidence/hosts/mac-coordinator-64gb-20260925/mac-coordinator-64gb-20260925--llama-cpp--use--20260927.json` at `14b5c521`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/14b5c52145d9cc42d4c9da36df53ac994009856a/evidence/hosts/mac-coordinator-64gb-20260925/mac-coordinator-64gb-20260925--llama-cpp--use--20260927.json) | Not ported; no host receipt or qualified-model entry is added |
| [`manifests/evidence.json` at `14b5c521`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/14b5c52145d9cc42d4c9da36df53ac994009856a/manifests/evidence.json) | Not ported; current main is used and only file registrations are added/refreshed |

`port-record-20261003.md` is new. Together with the nine source artifacts it
makes ten files in this directory. No `receipts[]` or `convergence_records[]`
entry is added.

## Scope comparison

| Source | Hosting or ownership scope | Boundary for these numbers |
| --- | --- | --- |
| #410's original proposal at `14b5c521` | The Mac hosts llama-embed with embeddinggemma on port 8232, Ollama `qwen3-embedding:4b` and `qwen3.5-9b-64k`, Qdrant and a 27B model; proposes Mac ownership of `model-hosting`, `memory-e2e` and `rag-e2e` | Historical proposal and observations; its host-role change and receipt are not accepted by this port |
| [2026-10-02 two-host north-star architecture](../../../docs/decisions/2026-10-02-two-host-north-star-architecture.md#responsibilities-on-the-two-hosts) | Retains the existing Mac ai-memory 2.5.2 owner and Ollama 0.34.4 as the measured control; macOS compute is limited to small reproducible fixtures and analysis; memory and gateway owners stay singular and nothing is relocated | Retaining an owner does not accept #410's hosting or qualification claims |
| [New-WSL definitive defaults](../../../docs/decisions/2026-10-01-new-wsl-definitive-defaults.md) | Ollama is the local model server; the embedding model is decided by measurement on that target | At this port's base, the record already reflects the preregistered settlement: Qwen3-Embedding-0.6B Q8_0 through Ollama as `qwen3-embedding-8k` at 8,192 context, and Swift-1.5-Qwen3.8-27B IQ3_S as `swift-iq3s-s2o-64k` at 64,000 context. Mac measurements establish neither target execution nor host acceptance |
| [Current workstation `owns` list](../../../adoption/host-roles.json) | `memory-e2e`, `rag-e2e`, `model-hosting`, `model-qualification`, `gpu-runtime-qualification`, `independent-review` | Separate routing/ownership source, not a consequence of this port |

No Mac number transfers to either the workstation's or the new WSL target's
acceptance. The current Mac `owns` list remains `macos-acceptance` and
`coordination`. This port makes no current-state claim about installed Mac
templates or processes.

## Unique facts from the unported decision record

The following are attributed to the Mac session on **2026-09-27**, not adopted
as a live decision. They retain the limitations in the corrected README.

The alternatives included borrowing workstation models over the network
(rejected in the source decision), serving the workstation's Nemotron embedder
(a supported-runtime gap at the examined revisions), and these three facts:

- Ollama's MLX engine was measured only for reranker latency: median **18.5 s**,
  compared with **27.9 s** for llama.cpp Metal at about **7.5K prompt tokens**;
  **1 of 3 calls** exceeded the **20 s** gate. The frozen li26 harness checked
  llama.cpp `/props`, so no Ollama li26 quality comparison was run.
- MLX-LM and LM Studio were not measured on this project's workload.
- Re-pinning macOS llama.cpp to b11146 was considered and not done.

All four original overturn conditions were a measurement on that Mac of:

1. Swap growth or a memorystatus kill under normal coordinator load with the
   co-resident set above.
2. A required model set whose weights and KV cache exceed the measured headroom.
3. The chosen memory reranker LLM missing ai-memory's 20 s gate at 4–8K tokens
   with more than 5% fallback, while a larger machine would meet it.
4. A supported Mac-native Nemotron-3-Embed (llama.cpp registration or NVIDIA
   GGUF/MLX) beating embeddinggemma on this project's retrieval comparison,
   with headroom to serve it.

Step 5 of #410's PR body also recorded pin drift, without changing pins:

- llama.cpp b11057 / b11146 / b11214. Its b11057 “cannot run C2” rationale is
  corrected: C2 was not run on that Mac install and no help/failure output was
  retained. Upstream b11057 registers `--spec-type` and `draft-mtp` at the
  verified source locations below; b11146 was the session's C2 trial runtime,
  and the co-residency build remains unresolved.
- Codex 0.155.1 / 0.157.1 / the ChatGPT-bundled 0.158.0-alpha.2.1.
- ai-memory 2.3.2 / 2.4.1 / build `19b6429`. The source README describes that
  local build as reporting 2.4.0, 46 commits ahead of and 62 behind official
  v2.4.1, with v2.4.0 as an ancestor; this is the recording session's account.
- Ollama `qwen3-embedding:4b` (2,560 dimensions) and llama.cpp embeddinggemma
  (768 dimensions) served different consumers and embedding spaces. The
  memory LLM was `qwen3.5-9b-64k`; the RAG embedder used port 8232.

These version comparisons are dated observations, not the current pins or a
replacement recommendation. The private host value file remains private.

## Status of the eight review findings

| Finding | Port disposition | Remaining work |
| --- | --- | --- |
| P1-1: no discriminating controls | Open for a Mac session through #379; qualification withheld | Run wrong-reference embedding and corrupted-li26 controls and retain the failing results with the passes |
| P1-2: li26 aggregates without per-filing rows/run hashes | Open for a Mac session through #379; quality/equality labelled reported summaries | Retain sanitized per-filing gold/prediction/status rows and hashes of every input/run file needed for independent derivation |
| P2-3: b11057 capability claim | Corrected | Source verification contradicts the old rationale; installation-scoped untested behavior is stated without claiming upstream absence |
| P2-4: embedding binary version not captured | Open for a Mac session through #379 | Capture the actual version line from the LaunchAgent executable; `llama_server: initializing ...` does not establish its build |
| P2-5: co-residency b11146/b11214 conflict | Marked unresolved | Resolve against retained or newly captured startup/version output; this port selects neither |
| P2-6: swap causation | Corrected | Build attribution is explicitly an inference from temporal overlap; the unsupported causal claim is removed |
| P2-7: gate execution conditions | Marked unknown | Complete launch/request parameters, generation limits, cache settings, observed concurrency and probe-driver/payload hashes are unavailable; per-call timings, `argv_extra`, the warm-up note and configured `providerConcurrency 4` are retained |
| P3-8: ownership recipe mismatch | Moot for this port | The proposed host-roles change is not ported; no recipe ownership change is needed |

## Evidence classes and what stays true on main

The [acceptance evidence policy](../../../docs/acceptance-evidence-policy.md#identify-what-each-check-proves)
classifies llama-bench as **Upstream example or native operation** on that host
on that date. `embed_acceptance.py`, li26 and the serving probe are each a
**Local integration check**. The gate is also a local integration check.
No embedding or li26 acceptance is inferred from a pass without a
discriminating control. The eight artifacts retain their original recording
labels byte-identically; their labels do not supersede the policy.

[The macOS next steps](../../../docs/next-host-stages.md#macos-next-steps-replacement-mac)
still hold: stage 2 services move only after #379's measurements and the
memory-layer head-to-head. The
[2026-09-27 single-writer staged decision](../../../docs/decisions/2026-09-27-mac-single-writer-staged.md)
still holds at its stage boundaries. No accepted #379 measurements are supplied
by this port, so its descriptive evidence does not satisfy those gates.
Both files remain unchanged, and #379 remains open with its existing labels.

## Verified sources and completeness check

- llama.cpp b11057 is tag
  [`59657a613ab0fa4ab327d6c790123dff30bfbd67`](https://github.com/ggml-org/llama.cpp/releases/tag/b11057).
  The exact tag source registers `--spec-type` at
  [`common/arg.cpp` L4235](https://github.com/ggml-org/llama.cpp/blob/59657a613ab0fa4ab327d6c790123dff30bfbd67/common/arg.cpp#L4235)
  and `draft-mtp` at
  [`common/speculative.cpp` L37](https://github.com/ggml-org/llama.cpp/blob/59657a613ab0fa4ab327d6c790123dff30bfbd67/common/speculative.cpp#L37).
- [Qwen3.8-27B-GGUF at `4ca720788d1e01f1bff70c033e0d0028fd02e502`](https://huggingface.co/unsloth/Qwen3.8-27B-GGUF/tree/4ca720788d1e01f1bff70c033e0d0028fd02e502)
  contains `Qwen3.8-27B-UD-Q4_K_M.gguf`.
- [embeddinggemma at `0f741b5a6585bd53aeb15cd1372c56f2a0f65e12`](https://huggingface.co/ggml-org/embeddinggemma-300M-GGUF/tree/0f741b5a6585bd53aeb15cd1372c56f2a0f65e12)
  contains `embeddinggemma-300M-Q8_0.gguf`.
- [Nemotron at `c0c9fea93ea424587517f2c59e20db9f1d6bf615`](https://huggingface.co/nvidia/Nemotron-3-Embed-1B-BF16/blob/c0c9fea93ea424587517f2c59e20db9f1d6bf615/config.json)
  declares `Ministral3Model`, `is_causal: false`, hidden size 2048. This is source
  review of a historical pin, not a current absence claim across all runtimes.

The bounded completeness check covered all 15 original files, all eight review
findings, the decision record's unique alternatives and four overturn
conditions, native-tool versus integration evidence, the Mac owner, the
measured WSL target and the separate workstation ownership source. The older
planning description of a still-undecided WSL embedder is superseded at this
port's base by the published measurement settlement; the comparison above
reflects that source. Missing controls, per-filing rows, private-run hashes,
version output and gate conditions remain the next Mac evidence sweep's scope.
No omitted runtime candidate is promoted through this historical port.

## Reopen path

The selected disposition is a descriptive port rather than importing the
original acceptance proposal or discarding the useful measurements. A new
controlled, independently reproducible Mac qualification is the comparison
that would overturn the withholding of acceptance.

A Mac session at a published main revision:

1. Runs discriminating controls, retains per-filing rows and input/run hashes,
   captures actual version lines and complete gate conditions, and resolves
   the co-residency build.
2. Records a new host receipt with `scripts/host_receipts.py record`, preserving
   returned results and independent observation under the evidence policy.
3. Proposes the host-roles change again through #379 with that native evidence.

This port does not activate services, relocate an owner, change a pin or close
the Mac host request.
