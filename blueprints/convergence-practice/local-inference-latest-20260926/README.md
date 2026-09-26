# Latest local models for 8-K item extraction: frozen preregistration

Frozen on 2026-09-26, before any download, inference or SEC request. This change
adds the plan, scripts and offline tests only. Nothing here has been measured.
One repair round, still before any run, amended the plan after independent review;
[`plan.json`](plan.json) lists every change under `amended_before_any_run`.

## GPU coordination

Another session owns GPU trials on this host until it records that they are done.
[`window.sh`](window.sh) refuses to start unless this README contains the exact
line `GPU trials: TRIALS DONE`. The coordinator replaces the status line below
when that session reports completion. Until then the line reads PENDING.

GPU trials: PENDING

## What and why

The production local generation endpoint (`nativestack-generation.service`) runs
Qwen3.8-27B UD-Q4_K_M on llama.cpp b11146 with 36 of 65 layers on the GPU. Its own
journal shows a median decode of 4.79 tokens/s and prompt processing of 61.5-146.1
tokens/s for 3,500-4,600-token prompts. This plan asks whether a newer serving
profile or a recent model is faster **without losing quality** on a north-star
workload: extracting the Form 8-K item codes a filing reports. Inference speed
alone does not pass. The arms are limited to the Qwen3.8 family and releases from
the past weeks, as the coordinator task of 2026-09-26 requested.

The workload is a proxy. Its labels are the filer-declared header `ITEMS`, not
hand-checked or frontier-model labels. It does not meet the catalyst-extraction
trial gate in `catalogs/us-equities/local-model-workloads-20260924.json`, and it
does not reopen any `skip_not_local` decision there.

## Arms

Every pin is a Hugging Face repository, a full revision and the file's LFS
SHA-256 and size, read from the Hugging Face API on 2026-09-26. The runtime for
every arm is the installed llama.cpp **b11146** (commit `7fe450e`, MIT). Full
pins, flag citations and memory estimates are in [`plan.json`](plan.json).

| Arm | What | File | Admission (free MiB) | Support on b11146 |
|---|---|---|---|---|
| C0 | Control: production model and profile, 36 GPU layers, 8192 context | `unsloth/Qwen3.8-27B-GGUF` `Qwen3.8-27B-UD-Q4_K_M.gguf`, 16,464,440,224 bytes, Apache-2.0 | 16,384 | runnable |
| C1 | Every layer and the output head on the GPU, dense FFN weights of blocks 0-19 on the CPU (`--gpu-layers 99 --n-cpu-ffn 20`) | same file | 17,151 | runnable if admitted |
| C2 | C1 plus MTP drafting from the main file's own MTP layer (`--spec-type draft-mtp --spec-draft-n-max 3`, no draft file) | same file | 17,535 | runnable if admitted; MTP context checked at startup |
| M | MiMo-V2.6-Distill-Qwen-9B, every layer on the GPU | `ggml-org/MiMo-V2.6-Distill-Qwen-9B-GGUF` `…-Q8_0.gguf`, 9,527,498,048 bytes, MIT | 16,384 | runnable (architecture `qwen35`) |
| B | PrismML Ternary Bonsai 2 27B | `prism-ml/Ternary-Bonsai-2-27B-gguf` `…-PTQ1_0.gguf`, 5,946,648,928 bytes, Apache-2.0 | – | **runtime_unsupported**: no `ptq1_0` type in b11146; the card requires the PrismML fork |
| X | Xing4.0-29B-A4B | `XingChen-AGI/Xing4.0-29B-A4B-GGUF` `xing4_0-29b-IQ4_NL.gguf`, 20,104,012,544 bytes, Apache-2.0 | – | **runtime_unsupported**: no `xing4_0` architecture in b11146 |

M uses Q8_0 because it is the only language-model quant in the official ggml-org
repository; it fits on the GPU within the admission floor. B uses PTQ1_0 because
its card measures it as the faster decode on an RTX 4090. B and X were not
downloaded; the pinned runtime's own source and type table exclude them. They
re-enter only under a new plan with a pinned runtime that supports them.

**Not arms.** Each has a recorded reason:

- **Qwen3.8-Flash-Next** (`resource_infeasible`). Its smallest 4-bit GGUF
  (UD-IQ4_XS) is 93,682,584,224 bytes and UD-Q4_K_XL is 111,334,654,784 bytes.
  WSL has 104,613 MiB in total and had 74,027 MiB available at planning, shared
  with the Polaris distribution.
- **C1 and C2 as tasked** (`resource_infeasible_on_host`). The task named
  `--gpu-layers 99` with no FFN offload, plus the MTP draft file
  `MTP/mtp-Qwen3.8-27B-Q4_0.gguf` for C2. With production stopped, at most
  24,143 − 3,930 = 20,213 MiB can ever be free beside the embeddings service: the
  device reports 24,143 MiB (422 are reserved) and vLLM holds its configured 0.16
  share. The tasked C1 needs 19,799 MiB, so the Windows side, whose display runs on
  this GPU, could hold at most 414 MiB. The draft file adds up to 1,306 MiB more.
  The draft file stays pinned in `plan.json` for a host with more device memory.
  The replacement C1 and C2 keep every layer on the GPU and move only the dense FFN
  weights of blocks 0-19 (2,648.8 MiB) to the CPU. Twenty is the fewest for which
  C2 is admitted with up to 2.5 GiB in use on the Windows side. C2 drafts from the
  trained MTP head already in the main file (`blk.64.nextn`), which b11146 uses
  without extra weights. C2 − C1 therefore isolates MTP drafting.

## Task and scoring

- **Cohort**: the frozen 2020-03-02 SEC daily index, whose hash, size and
  371/360/362/9 row, accession, 8-K and 8-K/A counts come from
  [`catalyst-dataset`](../../us-equities/catalyst-dataset/README.md). One accession
  is one filing, so n is at most 360.
- **Labels**: EdgarTools `FilingHeader.parse_from_sgml_text()` on the part of each
  `.hdr.sgml` header before its first `FILER` block, field `ITEMS`. The result must
  equal EdgarTools' own `collect_repeated_tags(header, "ITEMS")`. EdgarTools 5.58.0
  raises on headers with two or more `FILER` blocks, and the cohort has 9
  co-filings. `ITEMS` precede those blocks.
- **Input**: the first document of the filing's form type from the full
  submission, with the whole SEC header removed (its `ITEM INFORMATION` lines
  would reveal the labels), HTML reduced to text and whitespace normalized. Text
  over 16,000 characters keeps its first 12,000 and last 4,000 characters. That
  budget fits C0's 8,192-token slot beside the prompt and the 256-token reply;
  the tail keeps the closing items and signature block.
- **Exclusions**, in order: acquisition failure, empty primary document, zero
  declared `ITEMS`. The definitions are in `plan.json`.
- **Request**: one user message from [`prompt.txt`](prompt.txt); seed 0,
  temperature 0, top_k 1, top_p 1, `enable_thinking: false`, at most 256 output
  tokens, no grammar. The reply must be exactly `{"items": ["2.02", "9.01"]}`.
- **Scores**: per-filing precision, recall, F1 and exact match; micro-F1 over all
  filings; macro-F1 over codes declared by at least five filings; JSON-valid
  rate; median decode tokens/s (`timings.predicted_per_second`); time to first
  token (`timings.prompt_ms`); cold load seconds; peak whole-device memory from
  1 Hz `nvidia-smi` samples.
- **Server errors**: a context overflow (HTTP 400, `exceed_context_size_error`)
  is a per-filing invalid output. Any other HTTP error, a malformed reply, a
  request past 600 s or an unreachable server stops the arm and fails criterion
  (4). The pinned server answers a compute error with HTTP 500 and keeps serving.
  Raw error bodies stay private.

## Decision rule

An arm replaces C0 as the production generation model only if all four hold:

1. The paired bootstrap (10,000 resamples, seed 20260926) 95% lower bound of
   micro-F1(arm) − micro-F1(C0) is at least −0.02.
2. Its median decode tokens/s exceeds C0's.
3. Its JSON-valid rate is at least 0.98.
4. It had no memory or deadline failure. [`analyze.py`](analyze.py) scores this
   strictly. The arm's segments must cover every eligible filing, and it must have
   no guard, server-error, deadline or interruption event. Every started segment
   needs memory evidence: `memory.csv` present and well formed, samples at most
   30 s apart covering the server's run, none below 3,072 MiB free, and a verified
   `MemoryMax`.

If C1 or C2 passes, the model stays and only the serving profile changes. If
several arms pass, the fastest is selected. If C0 has not run, is still
incomplete, or has any failure, the result is inconclusive and nothing changes.

## Segments and expected duration

An arm runs in **segments** of at most one window each, and at most four in all.
A request starts only while 600 s remain before the segment's deadline, so a
segment ends between requests. The next `window.sh` run for that arm continues
from the first unattempted filing. It starts a fresh server with the same argv,
carries earlier results verbatim, and chains each segment's metrics to the
previous file by SHA-256. Only a clean boundary continues. After a completed,
failed or interrupted segment the arm never runs again. Admission refusals and
window-budget skips start nothing and may be retried in a later window.

C0 is slow at its production profile. The expected time per filing is
(720 + characters ÷ 3.5) ÷ prompt rate + 20 ÷ decode rate. For about 350 filings
of about 5,000 characters, the journal's rates give roughly 8,900 s (central),
15,500 s (slow) and 6,500 s (fast). **Two C0 segments are expected.** Four would
be needed only if every input were at the cap and every request ran at the
slowest observed rates. Compute the real estimate from the acquisition summary
(`eligible`, `input_chars_total`) before scheduling windows. C1, C2 and M are
expected to finish together in one window.

## How to run it on a GPU host

The commands below are frozen. None of them ran in this change. Set the path
variables first; use pointer variables and never spell out a credential store path:

```sh
CATALYST_SDK_PY=~/.local/share/codex-ecosystem/catalyst-provenance/sdk/bin/python
LI26_STATE=~/.local/state/native-agent-stack/local-inference-latest-20260926
MODELS_DIR=~/.local/share/codex-ecosystem/models
LLAMA_B11146=~/.local/share/codex-ecosystem/tools/llama-cpp-b11146-cuda12.8
```

1. **Acquire the filings once.** EdgarTools 5.58.0 fetches the daily index and,
   per accession, the header and the full submission: at most five requests per
   second, no automatic retries, and a stop at HTTP 403 or 429 or once more than
   36 accessions have failed. The run is complete only if the index hash and
   cohort counts match and at most 36 accessions failed. The contact comes
   from the `SEC_CONTACT_ENV` pointer file ([`docs/secret-storage.md`](../../../docs/secret-storage.md),
   row `sec-contact`) and is never printed. Keep the printed `inputs_sha256`.

   ```sh
   "$CATALYST_SDK_PY" blueprints/convergence-practice/local-inference-latest-20260926/acquire.py \
     --env-file "$SEC_CONTACT_ENV" --state-dir "$LI26_STATE" --run-id acq-<UTC date>
   ```

2. **Download M** at its pinned revision (`hf download`; the repository is
   public). C0, C1 and C2 use the installed production file.

   ```sh
   hf download ggml-org/MiMo-V2.6-Distill-Qwen-9B-GGUF MiMo-V2.6-Distill-Qwen-9B-Q8_0.gguf \
     --revision 81baddc39bc48924a88e87b8d31aceb03058e559 --local-dir "$MODELS_DIR/mimo-v2.6-distill-qwen-9b-81baddc"
   ```

3. **Free Windows-side GPU memory (coordinator only; required before every
   window).** At planning the Windows side held about 5,766 MiB. Admission allows
   at most 3,829 MiB there for C0 and M, 3,062 for C1 and 2,678 for C2.
   `window.sh` never closes anything. List processes with `tasklist.exe`. Pick the
   PIDs whose image name exactly matches wallpaper64 or wallpaperui, MuMuPlayer or
   MuMuVMMHeadless, chrome, the Adobe Creative Cloud helpers, or LogiOptionsPlus.
   Close each by PID with `taskkill.exe /PID <pid>` and record what was closed.
   Never close dwm, csrss, explorer, svchost or any other system host, vmwp,
   vmmem or WindowsTerminal. Never run `wsl --terminate` or `wsl --shutdown`, and
   never touch the Polaris distribution.

4. **Run the windows** after the coordination line above reads TRIALS DONE. Run
   `--arms C0` in as many windows as C0 needs. Each run continues automatically
   from the previous segment, and a run after C0 has completed is refused. Then
   run the other arms:

   ```sh
   bash blueprints/convergence-practice/local-inference-latest-20260926/window.sh --arms C0 \
     --acquisition "$LI26_STATE/sec/acq-<UTC date>" --inputs-sha256 <inputs_sha256> \
     --runtime-dir "$LLAMA_B11146" --models-dir "$MODELS_DIR" --state-dir "$LI26_STATE"
   bash blueprints/convergence-practice/local-inference-latest-20260926/window.sh --arms C1,C2,M \
     --acquisition "$LI26_STATE/sec/acq-<UTC date>" --inputs-sha256 <inputs_sha256> \
     --runtime-dir "$LLAMA_B11146" --models-dir "$MODELS_DIR" --state-dir "$LI26_STATE"
   ```

   Before touching anything, the window checks the following and refuses if any
   fails:
   - the coordination line;
   - every frozen hash, the acquisition, the runtime directory and the model files;
   - each arm's next segment;
   - that port 18299 is free;
   - the free memory predicted once production stops: the current free memory
     plus the production estimate of 9,478 MiB.

   Next it arms a transient timer, `li26-restore-<window>`. The timer fires three
   hours later, stops this window's arm scopes and starts production. So even a
   hung or killed script cannot leave production down. Only then does the window
   stop `nativestack-generation.service`, the only unit it accepts; it never
   touches `native-stack-embeddings.service` or any other unit.

   Each arm runs on `127.0.0.1:18299` in a `systemd-run --user --scope` with
   `MemoryMax=20G`, no swap, and a verified limit. It is admitted only if
   whole-device free memory is at least `max(16384, estimate + 3072)` MiB. A 1 Hz
   guard, each query bounded by 10 s, stops that scope if free memory falls below
   3,072 MiB or a query fails.

   The exit trap stops the arm, starts production, waits for `/health` 200 and
   cancels the timer. Every step in it is bounded. An INT or TERM during an arm
   records it as interrupted, which is final for that arm. On another host
   without the production unit, pass `--production-unit none`.

5. **Analyze** every window under the state directory. No attempt can be left out:

   ```sh
   python3 blueprints/convergence-practice/local-inference-latest-20260926/analyze.py \
     --state-dir "$LI26_STATE" --out <decision.json>
   ```

   The decision file marks `final: false` while an arm can still continue.

A new host must establish its own acquisition, downloads and hashes. This host's
planning facts are not its acceptance.

## Privacy boundary

- The SEC contact stays in its owner-only store file. `acquire.py` reads it from
  the pointer, uses it only as the EDGAR User-Agent inside its own process, and
  never prints, stores or hashes it into an output.
- SEC bytes, model inputs, raw model replies, server error bodies and server logs
  stay under `$LI26_STATE` with 0700 directories and 0600 files. Filing text
  never enters the repository.
- The public-safe outputs hold accession numbers, item codes, error types, counts,
  hashes and timings, never document text. They are the acquisition's
  `summary.json`, and `window-summary.json`, `window.json`, `memory.csv`,
  `eval/metrics.json` and the decision file. Registering them as receipts is a
  later change.

## Rollback

Production changes only if the rule passes. A window stops the production unit,
and its exit trap, or failing that the restore timer, restarts it. The unit file
is untouched and no drop-in is written. If a later adoption adds a serving-profile
or model drop-in, rollback removes that drop-in, runs
`systemctl --user daemon-reload`, restarts `nativestack-generation.service` and
checks `/health` 200. The current model file stays installed for that purpose.

## What this does not claim

No result exists yet. When results exist, they will not establish:

- frontier parity, or accuracy against hand-checked labels;
- catalyst or trading value, or historical availability;
- thinking-mode or long-context quality;
- isolated benchmark throughput, or any saving;
- any result for the tasked C1 and C2 profiles.

B and X have no result. Timing and memory are shared-host observations on a WSL2
desktop. The memory estimates are planning figures; the measured guard, not the
estimate, protects other GPU users.

## Files

| File | Role |
|---|---|
| [`plan.json`](plan.json) | Frozen arms, pins, profiles, sampling, task, rule, guards, host arithmetic, timing evidence and the SHA-256 of every script and the prompt |
| [`experiment.json`](experiment.json) | Planned convergence record (`scripts/validate_convergence.py`) |
| [`prompt.txt`](prompt.txt) | The frozen instruction; `@@FILING_TEXT@@` receives the input |
| [`acquire.py`](acquire.py) | SEC acquisition under the SDK Python; stdlib parsing helpers |
| [`eval_arm.py`](eval_arm.py) | One arm segment against the loopback server; argv builder, segment chain and preflight checks |
| [`analyze.py`](analyze.py) | Segment chains, memory evidence, paired bootstrap and decision |
| [`window.sh`](window.sh) | One GPU window with the restore timer and the production-unit trap |

Offline checks use synthetic fixtures and stand-ins only. The co-filer label check
runs EdgarTools only when the catalyst SDK is installed:
`uv run --no-project --with jsonschema --with pyyaml python -m unittest tests.test_local_inference_latest_20260926 -v`.
