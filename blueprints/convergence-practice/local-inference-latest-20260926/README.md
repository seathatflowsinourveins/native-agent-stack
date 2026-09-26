# Latest local models for 8-K item extraction: frozen preregistration

Frozen on 2026-09-26, before any download, inference or SEC request. This change
adds the plan, scripts and offline tests only. Nothing here has been measured.

## GPU coordination

Another session owns GPU trials on this host until it records that they are done.
[`window.sh`](window.sh) refuses to start unless this README contains the exact
line `GPU trials: TRIALS DONE`. The coordinator replaces the status line below
when that session reports completion. Until then the line reads PENDING.

GPU trials: PENDING

## What and why

The production local generation endpoint (`nativestack-generation.service`) runs
Qwen3.8-27B UD-Q4_K_M on llama.cpp b11146 with 36 of 65 layers on the GPU. It
decodes near 5 tokens/s. This plan asks whether a newer serving profile or a
recent model is faster **without losing quality** on a north-star workload:
extracting the Form 8-K item codes a filing reports. Inference speed alone does
not pass. The arms are limited to the Qwen3.8 family and releases from the past
weeks, as the coordinator task of 2026-09-26 requested.

The workload is a proxy. Its labels are the filer-declared header `ITEMS`, not
hand-checked or frontier-model labels. It does not meet the catalyst-extraction
trial gate in `catalogs/us-equities/local-model-workloads-20260924.json`, and it
does not reopen any `skip_not_local` decision there.

## Arms

Every pin is a Hugging Face repository, a full revision and the file's LFS
SHA-256 and size, read from the Hugging Face API on 2026-09-26. The runtime for
every arm is the installed llama.cpp **b11146** (commit `7fe450e`, MIT). Full
pins, flag citations and estimates are in [`plan.json`](plan.json).

| Arm | What | File | Support on b11146 |
|---|---|---|---|
| C0 | Control: production model and profile, 36 GPU layers, 8192 context | `unsloth/Qwen3.8-27B-GGUF` `Qwen3.8-27B-UD-Q4_K_M.gguf`, 16,464,440,224 bytes, Apache-2.0 | runnable |
| C1 | C0 with every layer on the GPU (`--gpu-layers 99`) | same file | runnable if admitted |
| C2 | C1 plus the official MTP draft (`--spec-type draft-mtp --spec-draft-model … --spec-draft-ngl 99 --spec-draft-n-max 3`) | adds `MTP/mtp-Qwen3.8-27B-Q4_0.gguf`, 1,369,590,656 bytes | runnable if admitted; draft load checked at run time |
| M | MiMo-V2.6-Distill-Qwen-9B, every layer on the GPU | `ggml-org/MiMo-V2.6-Distill-Qwen-9B-GGUF` `…-Q8_0.gguf`, 9,527,498,048 bytes, MIT | runnable (architecture `qwen35`) |
| B | PrismML Ternary Bonsai 2 27B | `prism-ml/Ternary-Bonsai-2-27B-gguf` `…-PTQ1_0.gguf`, 5,946,648,928 bytes, Apache-2.0 | **runtime_unsupported**: no `ptq1_0` type in b11146; the card requires the PrismML fork |
| X | Xing4.0-29B-A4B | `XingChen-AGI/Xing4.0-29B-A4B-GGUF` `xing4_0-29b-IQ4_NL.gguf`, 20,104,012,544 bytes, Apache-2.0 | **runtime_unsupported**: no `xing4_0` architecture in b11146 |

M uses Q8_0 because it is the only language-model quant in the official ggml-org
repository; it fits on the GPU within the admission floor. B uses PTQ1_0 because
its card measures it as the faster decode on an RTX 4090. B and X were not
downloaded; the pinned runtime's own source and type table exclude them. They
re-enter only under a new plan with a pinned runtime that supports them.

**Qwen3.8-Flash-Next is not an arm** (`resource_infeasible`). Its smallest 4-bit
GGUF (UD-IQ4_XS) is 93,682,584,224 bytes and UD-Q4_K_XL is 111,334,654,784
bytes. WSL has 104,613 MiB in total and had 74,027 MiB available at planning,
shared with the Polaris distribution; the GPU has 24,564 MiB.

The main UD-Q4_K_M file already carries one MTP layer, so b11146 could also draft
from it without the extra file. That cheaper profile is not an arm here.

## Task and scoring

- **Cohort**: the frozen 2020-03-02 SEC daily index, whose hash, size and
  371/360/362/9 row, accession, 8-K and 8-K/A counts come from
  [`catalyst-dataset`](../../us-equities/catalyst-dataset/README.md). One accession
  is one filing, so n is at most 360.
- **Labels**: `FilingHeader.parse_from_sgml_text()` on each `.hdr.sgml` header,
  field `ITEMS`.
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

## Decision rule

An arm replaces C0 as the production generation model only if all four hold:

1. The paired bootstrap (10,000 resamples, seed 20260926) 95% lower bound of
   micro-F1(arm) − micro-F1(C0) is at least −0.02.
2. Its median decode tokens/s exceeds C0's.
3. Its JSON-valid rate is at least 0.98.
4. It had no memory or deadline failure.

If C1 or C2 passes, the model stays and only the serving profile changes. If
several arms pass, the fastest is selected. If C0 fails or is not evaluated, the
result is inconclusive and nothing changes.

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

2. **Download the two new files** at their pinned revisions (`hf download`; both
   repositories are public). C0 and C1 reuse the installed production file.

   ```sh
   hf download unsloth/Qwen3.8-27B-GGUF MTP/mtp-Qwen3.8-27B-Q4_0.gguf \
     --revision 4ca720788d1e01f1bff70c033e0d0028fd02e502 --local-dir "$MODELS_DIR/qwen3.8-27b-4ca7207"
   hf download ggml-org/MiMo-V2.6-Distill-Qwen-9B-GGUF MiMo-V2.6-Distill-Qwen-9B-Q8_0.gguf \
     --revision 81baddc39bc48924a88e87b8d31aceb03058e559 --local-dir "$MODELS_DIR/mimo-v2.6-distill-qwen-9b-81baddc"
   ```

3. **Free Windows-side GPU memory (coordinator only, optional).** `window.sh` never
   does this. List processes with `tasklist.exe`, pick the PIDs whose image name
   exactly matches one of wallpaper64 and wallpaperui, MuMuPlayer and
   MuMuVMMHeadless, chrome, the Adobe Creative Cloud helpers, or LogiOptionsPlus,
   and close each by PID with `taskkill.exe /PID <pid>`. Record what was closed.
   Never close dwm, csrss, explorer, svchost or any other system host, vmwp,
   vmmem or WindowsTerminal. Never run `wsl --terminate` or `wsl --shutdown`, and
   never touch the Polaris distribution.

4. **Run the windows** after the coordination line above reads TRIALS DONE. Each
   window lasts at most three hours, so C0 runs alone first:

   ```sh
   bash blueprints/convergence-practice/local-inference-latest-20260926/window.sh --arms C0 \
     --acquisition "$LI26_STATE/sec/acq-<UTC date>" --inputs-sha256 <inputs_sha256> \
     --runtime-dir "$LLAMA_B11146" --models-dir "$MODELS_DIR" --state-dir "$LI26_STATE"
   bash blueprints/convergence-practice/local-inference-latest-20260926/window.sh --arms C1,C2,M \
     --acquisition "$LI26_STATE/sec/acq-<UTC date>" --inputs-sha256 <inputs_sha256> \
     --runtime-dir "$LLAMA_B11146" --models-dir "$MODELS_DIR" --state-dir "$LI26_STATE"
   ```

   Before touching anything, the window checks the coordination line, every frozen
   hash, the acquisition, the runtime directory and the model files, and that port
   18299 is free. Then it stops only `nativestack-generation.service`, and it
   never touches `native-stack-embeddings.service` or any other unit. It starts one
   arm at a time on `127.0.0.1:18299` in a `systemd-run --user --scope` with
   `MemoryMax=20G` and no swap, and verifies that limit. An arm is admitted only if
   whole-device free memory is at least `max(16384, estimate + 3072)` MiB: 16,384
   for C0 and M, 19,968 for C1 and 22,016 for C2. A 1 Hz guard stops that scope if
   free memory falls below 3,072 MiB. The exit trap always starts the production
   unit again and waits for `/health` 200. On another host without that unit, pass
   `--production-unit none`.

5. **Analyze** the arm directories under `$LI26_STATE/runs/`:

   ```sh
   python3 blueprints/convergence-practice/local-inference-latest-20260926/analyze.py \
     --arm-dir <C0 dir> --arm-dir <C1 dir> --arm-dir <C2 dir> --arm-dir <M dir> --out <decision.json>
   ```

A new host must establish its own acquisition, downloads and hashes. This host's
planning facts are not its acceptance.

## Privacy boundary

- The SEC contact stays in its owner-only store file. `acquire.py` reads it from
  the pointer, uses it only as the EDGAR User-Agent inside its own process, and
  never prints, stores or hashes it into an output.
- SEC bytes, model inputs, raw model replies and server logs stay under
  `$LI26_STATE` with 0700 directories and 0600 files. Filing text never enters
  the repository.
- The public-safe outputs are `summary.json` from the acquisition and
  `window-summary.json`, `window.json`, `memory.csv`, `eval/metrics.json` and the
  decision file. They hold accession numbers, item codes, counts, hashes and
  timings, never document text. Registering them as receipts is a later change.

## Rollback

Production changes only if the rule passes. A window stops the production unit
and its exit trap restarts it; the unit file is untouched and no drop-in is
written. If a later adoption adds a serving-profile or model drop-in, rollback
removes that drop-in, runs `systemctl --user daemon-reload`, restarts
`nativestack-generation.service` and checks `/health` 200. The current model
file stays installed for that purpose.

## What this does not claim

No result exists yet. When results exist, they will not establish frontier
parity or accuracy against hand-checked labels, catalyst or trading value,
historical availability, thinking-mode or long-context quality, isolated
benchmark throughput or any saving. B and X have no result. Timing and memory
are shared-host observations on a WSL2 desktop.

## Files

| File | Role |
|---|---|
| [`plan.json`](plan.json) | Frozen arms, pins, profiles, sampling, task, rule, guards and the SHA-256 of every script and the prompt |
| [`experiment.json`](experiment.json) | Planned convergence record (`scripts/validate_convergence.py`) |
| [`prompt.txt`](prompt.txt) | The frozen instruction; `@@FILING_TEXT@@` receives the input |
| [`acquire.py`](acquire.py) | SEC acquisition under the SDK Python; stdlib parsing helpers |
| [`eval_arm.py`](eval_arm.py) | One arm against the loopback server; argv builder and preflight checks |
| [`analyze.py`](analyze.py) | Paired bootstrap and decision |
| [`window.sh`](window.sh) | One GPU window with the production-unit trap |

Offline checks, which use synthetic fixtures only:
`uv run --no-project --with jsonschema --with pyyaml python -m unittest tests.test_local_inference_latest_20260926 -v`.
