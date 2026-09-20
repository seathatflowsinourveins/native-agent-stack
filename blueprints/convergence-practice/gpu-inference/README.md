# One local GPU inference lane

This lane qualifies one visible dependency-planner repair with a pinned Qwen
quant on a shared RTX 4090. It uses **partial CPU/GPU offload**, separate from the
native Codex/Claude clients. It does not route their model calls or alter their
accounts. Runtime installation, generated source, reviewed correctness and
performance each retain their own evidence.

On September 20, the single frozen trial generated a patch that passed independent
source review and all 12 unchanged tests. See the [acceptance](receipt.json),
unchanged [generation receipt](trial.json), [review](independent-review.json) and
[controlled test result](checks.json). Startup took 4.111 seconds, first content
6.818 seconds and generation 179.191 seconds for 394 output tokens. Generation
narrowly met the 180-second deadline; this profile is not an interactive default.
Minimum sampled free VRAM was 8,223 MiB, with no guard or cleanup errors.

The exact observed offloaded layer count is unknown: native verbosity 3 omitted
the detailed placement log. The 32-layer value is the configured limit, while
actual GPU allocation was observed. No second model run was made to improve the
receipt. The original generated-awaiting-review status is preserved in the
trial; the subsequent reviewed acceptance is recorded separately.

The frozen [plan](plan.json) sets 32 GPU layers, context 4096, one slot, batch 128,
eight CPU threads and a 1536-token output cap. Auto-fit is disabled. Admission
requires 16 GiB free device memory; a sampler guards a 3 GiB reserve and stops
only this lane's process on breach or deadline. Other GPU allocations remain
owned by their existing processes. Whole-device samples cannot guarantee that
no shorter unsampled peak occurred, or attribute every allocation to this job.

The [prompt](prompt.txt) uses the existing [seed fixture](../native-worker/seed/)
and unchanged 12-test oracle. Greedy sampling and disabled thinking are explicit
fixture settings, not an optimal benchmark recommendation. One trial has a
120-second startup deadline, 180-second generation deadline and 300-second
total deadline. Failures remain recorded; changing the profile requires a new
plan and separately authorized trial.

## Provenance and installation

The [preflight](preflight.json) records downloaded artifact hashes, native GitHub
attestation verification and license evidence. The exact runtime is upstream
**b11057 / 0.4.1-dev**, commit `59657a613ab0fa4ab327d6c790123dff30bfbd67`.
This is a dated prerelease trial, not a claim that the catalog's stable v0.4.1
changed. Its [official release](https://github.com/ggml-org/llama.cpp/releases/tag/b11057)
provides Ubuntu x64 CUDA 13.3 binaries and three accompanying CUDA libraries.
The stable v0.4.1-linked b10964 release lacks Linux CUDA archives.

Both archives were verified with native `gh attestation verify`, exact upstream
repository/source digest and rejection of self-hosted signing runners. The
certificate names the upstream release workflow and GitHub-hosted runner.
The binary archive carries MIT; the CUDA library archive carries no license
file, so the official [CUDA 13.3 EULA](https://docs.nvidia.com/cuda/archive/13.3.0/eula/index.html)
is retained in the private lane. Runtime/model archives and libraries are not
redistributed in this repository.

The model is [ggml-org's Qwen3.8-27B Q4_K_M conversion](https://huggingface.co/ggml-org/Qwen3.8-27B-GGUF/tree/efbb3b1f70a21d97fd4495240648405f7228554f),
revision `efbb3b1f70a21d97fd4495240648405f7228554f`. Its primary source revision
matches [Qwen's Apache-2.0 model](https://huggingface.co/Qwen/Qwen3.8-27B/tree/1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0).
Only the 18,973,870,528-byte text quant is selected; no vision projector, draft
model or MTP weights are needed. Cached search metadata disagreed with the
current model hash, so immutable metadata and actual downloaded bytes control.

The private installation is one versioned user-owned directory with downloads,
runtime, licenses and trial output. Native libraries are scoped to the server
process. No Linux driver, full toolkit, Python framework, global linker change,
shell startup modification or daemon is required. Downloads are HTTPS-only,
resumable and time-capped; partial bytes remain available after failure.

For a new host, first verify the same immutable archive/model bytes and licenses,
verify upstream attestations, inspect archive paths and extract with safe data
filtering. Run native version/device discovery before inference. Metadata and
this host's recorded result do not establish another host's compatibility.
The new host must satisfy the frozen hardware/resource preflight itself.

## Explicit execution and review boundary

The [runner](qualify.py) only starts a loopback native server, sends one bounded
request, measures it and saves source for review. Its AST check is a filter,
**not a sandbox** or semantic proof. It never imports or executes generated code.
Native agent tools, web UI and automatic model downloads are disabled or avoided.
The server exits at the end; private logs and request data stay outside Git.

After the private lane contains verified artifacts and the frozen plan/prompt:

```sh
python3 qualify.py --lane "$GPU_LANE" --plan plan.json --prompt prompt.txt
```

For audit/reproduction, the runner's foreground native command is below. The
runner supplies the memory/deadline guard and scoped cleanup; this bare command
alone does not. Set `GPU_LANE` to the explicitly selected private installation:

```sh
env -i PATH=/usr/bin:/bin HOME="$GPU_LANE" CUDA_VISIBLE_DEVICES=0 \
  LD_LIBRARY_PATH="$GPU_LANE/runtime/cudart-llama-b11057-bin-ubuntu-cuda-13.3-x64" \
  "$GPU_LANE/runtime/llama-b11057/llama-server" \
  --model "$GPU_LANE/downloads/Qwen3.8-27B-Q4_K_M.gguf" \
  --alias local-qwen38-frozen --host 127.0.0.1 --port 18085 \
  --ctx-size 4096 --parallel 1 --n-gpu-layers 32 \
  --batch-size 128 --ubatch-size 128 --threads 8 --n-predict 1536 \
  --fit off --no-webui --no-agent --jinja --perf
```

An existing `trial.json` prevents overwriting/replaying an attempt. Review the
returned source independently, then copy only that source plus the unchanged
oracle into a fresh controlled directory and run the oracle with a deadline,
minimal environment and resource limits. Preserve the original failed seed and
all source hashes. A passing static filter alone never authorizes execution.

The receipt reports actual offloaded layers from native logs, cold startup,
first content and generation latency, native usage, sampled peak device memory,
cleanup errors and observed final memory. Unknown telemetry stays unknown.
Numbers with unrelated device activity are shared-host observations, not an
isolated performance benchmark. There is no baseline or token savings claim.

Offline checks are `python3 -m unittest tests.test_gpu_inference -v`. They exercise
frozen resource limits, prompt/oracle hashes, source filtering and failure-safe
cleanup without any model calls.

Rollback affects only the versioned private lane after its owned process has
exited. Preserve compact receipts and any deliberately retained model cache;
no global service or driver restoration is needed.
