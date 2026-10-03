# Preregistration: local generation model and embedding model of the new WSL

Written before any trial. Slots: `local-generation-model` and `embedding-model` of the definitive manifest
(`evidence/artifacts/new-wsl-definitive-defaults-20261001/definitive-manifest.json` on main `cdc8319b`), both `split`.
The tests are the ones the manifest names for these slots (`deciding_measurement`), in the words of the critic record
`evidence/artifacts/new-wsl-final-architecture-20261002/critics/added-critics-result.json`
(sha256 `ed444353fae463da52f5f461fb5975eb5d607260d6c219407e77567255b69622`). Nothing here adds an arm or changes a rule;
it fixes the values the critic left open.

## Conditions (both parts)

- Host: the throwaway distribution (Ubuntu 26.04.1, merged recipe, WSL 3.0.1.0), RTX 4090, 24 GB.
- The GPU is free of other holders: `nvidia-smi --query-gpu=memory.used` prints under 600 MiB before the first load.
  The workstation's generation and embedding services hold GPU memory today, so the run needs a window in which they
  are stopped. That is the user's decision; without it nothing in this document runs.
- Server: Ollama 0.35.0 from the install plan, `OLLAMA_CONTEXT_LENGTH=64000`, one server process.
- Models by library tag, with the digest that `ollama list` prints recorded before the first trial:
  `qwen3.8:27b`, `gpt-oss:20b`, `qwen3-embedding:0.6b`, `embeddinggemma`.
- Every command, its output and its exit code are kept; a failed call is a result, not a retry.

## Part A: generation model

Arms: `qwen3.8:27b` (Q4_K_M) and `gpt-oss:20b`. The record's rule: gpt-oss:20b takes the slot if Qwen offloads to CPU or
evicts the embedder at 64k, or has the lower valid tool-call rate.

**A1. Co-residency at 64k (first; it can decide alone).** For each arm, from a server with nothing loaded:
1. load `qwen3-embedding:0.6b` with `keep_alive: -1` through `/api/embed`;
2. load the arm through `/api/generate` with `num_ctx: 64000`, `keep_alive: -1`, and generate 64 tokens from a prompt of
   about 60,000 tokens (a fixed public text, its sha256 recorded), so the cache is used and not only allocated;
3. record `ollama ps`, `nvidia-smi --query-gpu=memory.used,memory.total` and the server log lines for the load.

An arm passes A1 when `ollama ps` lists both models, each at `100% GPU`, after step 2. Qwen failing A1 gives the slot
to gpt-oss:20b if gpt-oss:20b passes A1. If both fail, the slot stays split and the record says so.

**A2. Tool calls (only if both arms pass A1).** One fixed set, the same cases for both arms, through three surfaces of the
one server: `/v1/chat/completions` with a JSON schema, `/v1/responses` and `/v1/messages`.
- Cases: the `simple` category of the Berkeley Function-Calling Leaderboard as packaged for Inspect AI (the manifest's
  owner for model evaluations), the first 100 cases after a shuffle with seed 20260927, run once per surface through
  Inspect's providers for that surface. If that package cannot address one of the three surfaces, that surface is
  reported as `not evaluated` with the reason, and the comparison uses the surfaces both arms ran on.
- Client request shapes: the two real clients against the same server, five fixed repository tasks each (create a
  file, edit a file, run a command and report its output, read a file and answer, a two-step edit that depends on a
  command's output), in a fresh scratch repository per task. Codex runs with its built-in local-provider option;
  Claude Code runs through the server's documented launch entry. A task passes when a fixed file check passes.
  These need the two clients present in the distribution; no sign-in is needed for a local model.
- Primary metric: first-pass valid tool calls (the call parses, names an offered tool, and its arguments satisfy the
  schema; no repair, no retry; an HTTP 500 counts as invalid), as a share of all cases over the surfaces run.
- Also recorded, not deciding: task success, tokens per second, peak GPU memory.
- Rule: the arm with the higher primary share takes the slot. A difference whose 95% paired bootstrap interval over
  cases (10,000 resamples, seed 20260927) includes zero is a tie, and a tie goes to the arm with more free GPU memory
  at 64k with the embedder resident.

## Part B: embedding model

Arms: `qwen3-embedding:0.6b` and `embeddinggemma` through the one server; Nemotron-3-Embed-1B through a second server.
The record's rule: a model that needs a second model server must beat the best single-server model by an interval
that excludes zero.

- Retrieval set, fixed now: the MTEB task `CQADupstackUnixRetrieval` (BEIR's CQADupStack, Unix forum; technical
  English questions against forum posts), test split, at the MTEB release current on the run date, its version recorded.
  Reason for this set: public, standard, small enough for three arms in one window, and closer to developer text
  than the other small BEIR sets.
- Runner: MTEB, unmodified, with an encoder that calls each model's served route (`/api/embed` for the two Ollama arms).
  Inputs are truncated to each model's documented limit by the server; no chunking, no reranker.
- The generation model that took Part A is resident during every run (`keep_alive: -1`).
- Primary metric: nDCG@10, the task's main score. Interval: paired bootstrap over queries, 10,000 resamples, seed
  20260927.
- Rule: between the two single-server arms the higher nDCG@10 takes the slot; if the interval of their difference
  includes zero, the arm with the smaller resident GPU memory takes it. Nemotron-3-Embed-1B takes the slot only if
  its difference to that arm has an interval above zero; it is run only if the GPU holds it beside the generation
  model, otherwise it is recorded as `does not fit beside the generation model` and is out.

## What is installed afterwards

The two winners are pulled in the final distribution with `ollama pull`; no other model is. The manifest rows change
from `split` to the measured default in a pull request that carries this document, the raw records' hashes and the
compact result. The throwaway distribution is removed after the open measurements are done.

## Not established by this measurement

Coding-task quality of either generation model; multilingual retrieval; behaviour at contexts above 64k; speed under
concurrent requests.

## Amendment 1, 2026-10-02T18:06:14Z, before any trial

Observed when the window was opened: with the workstation's two model services stopped and nothing loaded in the
measurement server, `nvidia-smi` still shows about 5,000 MiB in use. No WSL process holds it; it belongs to the
Windows applications the user works with (browser, desktop applications). The condition "under 600 MiB" above would
need those applications closed, and the user is working in them now.

A local model that only fits on an empty GPU is not a working fallback on this host, so the test is run under the
condition the host is normally in, and the rule is stated for it before the first load:

- **Condition N (normal, run now):** no WSL process other than the server under test holds GPU memory; the Windows
  applications stay as the user has them; the memory in use before the first load is recorded.
- **Condition F (free GPU, later and only with the user's word to close those applications):** as written above, under
  600 MiB. It is informative; it does not decide the default.
- **Rule under N:** an arm that fails A1 under N cannot take the slot. If only one arm passes A1 under N, it takes the
  slot. If both pass, A2 decides as written. If neither passes, the slot stays split.
- Part B runs under N with the arm that took Part A resident.

Everything else stands. No trial has run before this amendment.

## Result of A1 under condition N, and amendment 2, 2026-10-02T18:10:09Z

A1 as written ran once at 18:06Z to 18:09Z (raw/M6-a1.txt). Neither arm met the pass rule: `qwen3.8:27b` at a 64k
context was at 92.6% GPU (size 18.36 GB, 16.99 GB on the GPU) and the embedder was no longer listed; `gpt-oss:20b`
was fully on the GPU (12.97 GB) with about 7 GB free, but the embedder was no longer listed either. The server's log
says that it evicted a model on a prediction of memory, although the predicted size was below the free memory it
logged. By the rule, the slot stays split on this trial. That result stands and is not replaced.

The written order (embedder first, then the generation model) is not the order in which the system is used: the
generation model stays resident and the embedder is called on demand. Whether the two can be resident together is
therefore not answered for `gpt-oss:20b` by the trial above. Diagnostic A1b, stated before it runs:

- For each arm, from a server with nothing loaded: load the arm (num_ctx 64000, keep_alive -1, a short prompt), then
  call the embedder (keep_alive -1), then call the arm again with the long prompt of A1. Record `/api/ps` after
  each call.
- A1b passes for an arm when, after the last call, both models are listed and each is fully on the GPU.
- Rule: A1b is a diagnostic of the server's scheduling. An arm that passes A1b and failed A1 only by the embedder's
  eviction is recorded as "co-resident in the order of use"; the slot's decision then follows the rule of amendment 1
  with A1b in place of A1, and the record keeps both trials. An arm that is not fully on the GPU in A1b fails.

## Result of A1b, and amendment 3, 2026-10-02T19:18:52Z, before any trial of a new arm

**Result of A1b (18:10Z to 18:16Z, raw/M6-a1b.txt, sha256 fedf12982d944ffb2626497ec42e7c42e37bf517b1732cce58a346477b647808;
A1's record raw/M6-a1.txt, sha256 55be56478eaa6530fab4fe97871b09df9bcd7cb497aefba1bfbede618a976848).** In the order of
use `gpt-oss:20b` was fully on the GPU with the embedder resident beside it (108.9 output tokens per second) and
passes; `qwen3.8:27b` was at 92.6% GPU and fails. By the rule of amendments 1 and 2, `gpt-oss:20b` takes the
generation slot, and A2 was not needed because only one arm passed. That result stands and is not replaced by
anything below. One finding for configuration: with the server-wide context of 64,000 the embedder loaded at its full
context and took 5.78 GB; the context belongs to each model, not to the server.

**Why the comparison is extended.** At about 18:20Z the owner told the coordinator, verbatim: "please only using the
latest sota models, with newest advanced releases, you can use the hf key and essential stacks it related repos of
local model optimization etc". Both arms above come from an earlier round. The slot proposal that rested on the
result is withdrawn, the result is kept as a historical result, and new arms enter. They were selected from primary
sources by the Codex lane (its stronger model at maximum effort), not by this session: note
`CODEX-LOCAL-MODEL-COMPARISON-PREPARATION-20261002.md`, sha256
54edcfc8ced3ac4ce582af9f05fb57f46f99cd4aed58da09e653f350c4258b09. Its ranking is a preparation priority, not a
quality verdict. A newer release date is not a quality result either.

### Arms of the extension (an arm is a system: model file plus runtime)

- **S1, Bonsai:** `prism-ml/Ternary-Bonsai-2-27B-gguf` at revision `b072e1d3b35a0a630cece372c2127528e0994386`, packing
  PTQ1_0 (5,946,648,928 bytes), served by the runtime its publisher names: PrismML's llama.cpp at
  `adfffbe41b2cabcd51fff326ab045662265062bb` (release `prism-b10743-adfffbe`). This is a second model server beside the
  manifest's one.
- **S1b, declared now and run only on a stated condition:** the same model in packing PQ2_0 (7,206,168,928 bytes), same
  runtime. It runs only if S1 fails G0 or A1, as its own arm; its results are reported beside S1's failure and never
  replace S1's reported result.
- **S2, Swift:** `ukisai/Swift-1.5-Qwen3.8-27B-GSQ-RCO-GGUF` at revision `d74895bbe5db4bec1e0024e7cc87d59c02d7631a`,
  IQ3_S without MTP (11,771,546,912 bytes), served by the runtime that the freeze sheet names from its card. If that
  is the manifest's server, S2 is a single-server arm; otherwise it is a second-server arm.
- **C, control:** `gpt-oss:20b` on Ollama 0.35.0, the holder of the historical result. It is not a newest-release
  selection. It runs A2 so that the new arms have a baseline measured under the same rules.
- Not arms, with the reason recorded in the Codex note: the reviewed MiMo, GLM-5.3 and IQuest-Q1 weight files cannot
  be fully resident in 24 GB; Xing4.0's official quantization has no headroom shown under condition N, and its smaller
  community quantization needs another fork whose support was unmerged upstream.

### Frozen for every arm

- Condition N of amendment 1, the load order of amendment 2 (generation model first, then the embedder, then the long
  prompt), the fixed prompt of A1, the cases, seed and bootstrap of A2, and Part B's retrieval set: unchanged.
- Context: the literal 64,000 tokens for every generation arm, not 65,536.
- The embedder is loaded with its own context, set per model in the request or its model file, never through a
  server-wide setting; the value is on the freeze sheet.
- Key-value cache at 16-bit floats on every arm; no experimental quantized cache and no format conversion to make an
  arm fit. One request at a time (one slot, no parallel requests).
- Every command, output and exit code is kept; a failed call or a retry is a result with its usage, not a repeat.

### Gates and order

- **G0, function gate, for every arm that is not served by the manifest's server.** The gate that settled the
  model-server slot (`evidence/artifacts/local-model-server-gate-confirmatory-20261001`, wall limit 1,200 seconds),
  with its pass rule unchanged: "A run passes when its codex exec --json event log has a completed mcp_tool_call item
  for server time, tool get_current_time, with a result carrying a datetime string, and the last agent_message
  contains that string. An arm passes when all three scored runs pass. A run that reaches the wall limit fails. No run
  is repeated, excluded or re-scored." It runs with the arm's own model file and runtime at a context of 64,000. An arm
  that fails G0 cannot take the slot: the Codex client could not use its tools through that server.
- **A1 in the order of use** (the procedure of amendment 2) under condition N. An arm passes when, after the long
  prompt, the generation model and the embedder are both resident and each is fully on the GPU, as its own server
  reports it and as `nvidia-smi` shows it; for a second-server arm the embedder is the manifest server's.
- **A2, tool calls, required for every arm that passes A1, also when only one arm passes** (this replaces "only if
  both arms pass A1"). Cases, surfaces, client tasks, primary metric and interval are those of Part A2. A surface that
  a runtime does not serve is reported as not evaluated with the reason. A memory probe of 64 output tokens is not a
  task result: an arm that passes A1 and produces no valid tool call in A2 fails.

### Decision rule of the extension

1. An arm that fails G0 (where it applies), A1 or A2's floor (no valid tool call at all) cannot take the slot.
2. Among the arms that remain, the higher A2 primary share takes the slot; a difference whose 95% paired bootstrap
   interval includes zero is a tie, and a tie goes to the arm with more free GPU memory at 64,000 with the embedder
   resident, as Part A2 says.
3. Second-server rule, the same as Part B's and as the manifest's rule for an option that installs something extra:
   an arm that needs a second model server takes the slot only if its A2 difference to the best single-server arm
   has an interval above zero. Otherwise the best single-server arm takes it.
4. A measured difference is a difference between systems. The record does not attribute it to the weights alone
   where the runtimes differ.
5. If no new arm qualifies, the record says so, the historical result stays the only measured holder, and the choice
   between an older model that qualifies and no local fallback goes to the owner.

### Part B

The embedding and reranker arms from the newest releases are under source review in the Codex lane. They are frozen
in a further amendment before Part B runs; Part B's set, runner, metric and rules are unchanged, and the generation
arm that takes Part A is resident during it.

### Not frozen yet: the freeze sheet

These are inputs, not passed gates: the file names and hashes of the Bonsai packings; the Prism runtime's build
recipe and the hash of the built server; Swift's supported runtime, template and tool-call parser; the reasoning
setting for Bonsai, whose own notes report malformed or looping tool calls and server errors at high reasoning; the
sampling values and the output budget per arm; the embedder's context value; the endpoints each runtime serves. They
are written with their sources on a freeze sheet, appended here as amendment 3a and hashed before the first download
of weights and before the first load. No trial of a new arm runs before that hash is posted.

### What this extension does not establish

Independent evaluations of these exact quantization and runtime pairs were not found by the Codex lane's review.
Arithmetic on file sizes and cache sizes is not measured memory. Nothing here is a statement about coding quality,
throughput under concurrent requests, or behaviour above 64,000 tokens.

## Amendment 3a: freeze sheet for G0 and A1, written 2026-10-02T19:39:30Z, before any download of weights

Every literal below was read from its source on 2026-10-02 (the model repositories and the runtime release through
their APIs, the publisher's scripts at the named commit, this repository's gate at main `b5079894`), or was printed
by a command in the measurement distribution that loaded no model (raw/M7-prism-runtime.txt, sha256
f1161c923033922be2b75239e92ea1cd6d45982730a62c43ae0898afcf9cd686; raw/M7b-cuda-runtime.txt, sha256
c2fa03a79b3b04f3db95a8799b9d0754e4b49adfe75a3e7bbbf0feef93580401). The Codex lane raised no objection to the rules of
amendment 3 and to the function and second-server gates (its hand-off of 19:35Z).

### Files (each checked against this hash after download, before any load)

| Arm | File | Bytes | sha256 |
| --- | --- | --- | --- |
| S1 | `Ternary-Bonsai-2-27B-PTQ1_0.gguf` | 5,946,648,928 | `53107f530aa52eb00912263ab1ee29bd199261c87cd7b4ad4ca1318c1fe33ee3` |
| S1b | `Ternary-Bonsai-2-27B-PQ2_0.gguf` | 7,206,168,928 | `3907dc1658db1f78a9826bf8d5bcb8dc65db0d466388937af57f2294fae62ec1` |
| S2, S2o | `Swift-1.5-Qwen3.8-27B-GSQ-RCO-IQ3_S.gguf` | 11,771,546,912 | `1333c6ea70ef348d4ac6d62732772e8ad6571ac5b3754c14ed54f1a0d904a786` |

Repositories and revisions as in amendment 3. Neither repository is gated or private (their API fields, read today),
so no sign-in is needed. Licences, recorded and not a criterion: Bonsai Apache-2.0; Swift "Swift Open License v1.0"
with the original Qwen parts under Apache-2.0. S1b is downloaded only if its condition occurs.

### Runtime of S1, S1b and S2: PrismML llama.cpp

- Release `prism-b10743-adfffbe`, commit `adfffbe41b2cabcd51fff326ab045662265062bb`, archive
  `llama-prism-b10743-adfffbe-bin-linux-cuda-12.8-x64.tar.gz`, sha256
  `43b73a24d5cd83c4482750ee52e59afac497c669c008a319e44e43a0033757e2` (the release's published digest; the download
  matched). The CUDA 12.8 build is the one the model's known-issues file recommends on Linux.
- Server binary `llama-server`, sha256 `f0321669b20397593e3ac09972bf6f4b7a0684954906565353b7ca84b4b0320f`; it prints
  `version: 0.2.0-dev (build 10743, commit adfffbe41)` and lists `CUDA0: NVIDIA GeForce RTX 4090`.
- The archive carries no CUDA runtime. Supplied without a system CUDA install: NVIDIA's wheels
  `nvidia-cuda-runtime-cu12` 12.8.90 and `nvidia-cublas-cu12` 12.8.5.5 (with `nvidia-cuda-nvrtc-cu12` 12.9.86 as their
  dependency) unpacked into a folder on the library path (`libcudart.so.12` sha256 c3a75b33…9920, `libcublas.so.12`
  18a5df54…8e5c, `libcublasLt.so.12` 974927b9…0a4d, full values in raw/M7b), and Ubuntu's `libgomp1`
  16-20260322-1ubuntu1.
- S2's card asks for "a llama.cpp build that supports Qwen3.8" and names no version. The frozen reading: this same
  build, a llama.cpp fork whose own model is built on Qwen3.8-27B. If it does not load the file, S2 is recorded as not
  loadable on the frozen runtime and is out; no other llama.cpp build is substituted after that outcome.

### Server commands

- S1 and S1b, the publisher's start line for this model (`scripts/start_llama_server.sh` of `PrismML-Eng/Bonsai-demo`
  at `bfaea577522626b883f755236878e4583f3d6e68`) with these declared differences: the literal context, one slot, the
  cache type written out, no web-interface configuration and no image projector:
  `llama-server -m <file> --host 127.0.0.1 --port <port> -ngl 99 -fa on -c 64000 --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.05 --jinja -np 1 -ctk f16 -ctv f16`
- S2, the card's command with the same declared differences:
  `llama-server -m <file> --host 127.0.0.1 --port <port> -ngl 99 -fa on -c 64000 --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 --presence-penalty 0.0 --repeat-penalty 1.0 --jinja -np 1 -ctk f16 -ctv f16`
- The server's reasoning switch stays at its default (`auto`), and no reasoning budget is set on the server.
- C and S2o: Ollama 0.35.0 as the measurement distribution's user unit, restarted for this extension without the
  server-wide context setting; `OLLAMA_KEEP_ALIVE=-1` and one parallel request stay. The generation context of 64,000
  is sent with each request.

### One more declared arm: S2o, Swift on the manifest's server

The same Swift file imported into Ollama 0.35.0 with a model file that takes every line of
`ollama show --modelfile qwen3.8:27b` except its `FROM` line, which names the Swift file. It is a single-server arm.
Import gate, before anything else: `ollama create` exits 0 and `ollama show` lists the capability `tools`. If the
gate fails, S2o is recorded as not importable and is out. The publisher documents no Ollama route, so a result of S2o
is a result of this system and says nothing about the publisher's supported route (S2).

### Requests

- Reasoning effort `medium` on every request that can carry the field, for every arm: Bonsai's notes say `high`
  returns HTTP 500 and recommend `medium` at an output limit near 16,000 tokens. Where a surface or a server rejects
  the field, the rejection is recorded and the arm runs at its template's default on that surface.
- Output limit 16,384 tokens for G0 and, later, A2. A1 keeps its 64 output tokens: it measures residency, not answers.
- The embedder is `qwen3-embedding:0.6b` on Ollama with `num_ctx` 8192 in the embedding request (its documented
  maximum is 32K; the card's own example uses 8192).
- Model digests are those `ollama list` prints, recorded again before the first trial of this extension.

### G0 as run here

The files of `evidence/artifacts/local-model-server-gate-confirmatory-20261001` at main `b5079894`, copied into the
measurement folder. Unchanged, byte for byte: the scorer `gate_score.py` (sha256
44f19bcc4c43c5e40c2b737423adac6b1b0cd008dcfb4f06753049ca14672da8), the prompt, the wall limit of 1,200 seconds, one
unscored warm-up and three scored runs, `mcp-server-time` 2026.8.18, no run repeated, excluded or re-scored.
Declared differences, each because the arm differs from the gate's own arm:

1. Only the llama-server arm runs, per system arm: labels `warmup`, then 1, 2, 3.
2. Server binary, model file, alias and sampling flags are the arm's (above); the library path carries the CUDA
   runtime; the GPU is used (`-ngl 99 -fa on`) where the gate ran on the CPU.
3. Context 64,000 in the server command and in the client's model description, where the gate had 32,768.
4. The client is the Codex CLI installed in the measurement distribution by the install plan (0.160.0), where the
   gate pinned 0.159.3. Its profile is the one Ollama's launcher writes for the control model, with the provider name,
   the address and the model name replaced, as the gate derives its llama profile; the reasoning effort in it is
   `medium`.
5. The adapted copies of `gate_env.sh`, `gate_setup.sh` and `gate_run.sh` are hashed and listed in the run record
   before the warm-up.

G0 runs first for S1 and S2. S1b runs G0 only on its condition. C and S2o are served by the manifest's server and do
not run G0.

### A1 for a second-server arm

The generation model is on the Prism server and the embedder on Ollama. The arm passes when, after the long prompt,
the Prism server's log reports every layer offloaded to the GPU, `nvidia-smi` lists its process with its memory, and
Ollama's `/api/ps` lists the embedder with all of its size on the GPU. The memory in use before the first load, the
memory of each process and the free memory after the long prompt are recorded.

### Order and windows

Downloads first, with their hashes. Then, with the workstation's two model services stopped for the window: G0 for
S1 and S2 (and S1b on its condition); the import gate for S2o; A1 for every arm still in; C's A1b result of today
stands and is not rerun. A2's materials (the task texts and their file checks, the evaluation package versions) are
frozen in amendment 3b before the first A2 run and are the same for every arm; A2 may run in later windows, one arm
and one surface at a time, and no decision is taken before all of it has run.

## Deviation 1, 2026-10-02T19:50:03Z: the first G0 window opened under a condition that was not met

**What happened.** The window for G0 (S1, then S2) was opened at 19:47:42Z. Its log shows 18,094 MiB of GPU memory in
use after the workstation's two services were stopped and before the first load (raw/_gpu-window.txt). Condition N
requires that no WSL process other than the server under test holds GPU memory. One did: the measurement
distribution's own Ollama server still held `gpt-oss:20b` (11.92 GiB on the GPU, raw/M11x-abort.txt), resident since
the A1b trial at 18:16Z, whose script ended without unloading it and whose server keeps models loaded indefinitely.
The window script recorded the memory figure and did not check it. That is this session's error.

**What was done.** The window was stopped at 19:48:54Z, on the memory figure alone, and the gate's processes in the
measurement distribution were ended at 19:49:07Z. At that moment S1's unscored warm-up had finished and its first
scored run had started; no llama-server process was alive beside the client. No score file and no event log of
that attempt was opened by this session before this note was written. The model was unloaded (0 models resident
afterwards) and the workstation's two services were active again at 19:48:54Z. S2 had not started.

**How it is handled.**

- The attempt is void because its precondition was not met, a fact fixed by the log line written before the first
  load; it is not void because of anything it returned. Its state folder is kept unchanged under a new name
  (`g0/S1-void-20261002T1949Z`) and is reported with the results, including whatever its files show.
- S1's G0 runs again from a freshly prepared state folder, with the same frozen files, commands and rules. The gate's
  rule that no run is repeated, excluded or re-scored applies within a valid attempt, as before.
- From now on the window does not start a load unless these hold, checked by the script and written to its log:
  the measurement Ollama server lists no resident model, no llama-server process exists in the measurement
  distribution, and the workstation's two services are inactive. The GPU memory in use at that moment is recorded;
  under condition N it is whatever the Windows applications hold and is not a pass criterion.
- Scripts that load a model through Ollama for a trial unload it at their end.

Records: raw/_gpu-window.txt (sha256 at this note b10e1388d7b1a833ce14b42c3a6939e8d79773892b724f8f300cfd618b72d2a8),
raw/M11x-abort.txt (fe735e0cfbbdcf569380f8104f53a5de47d98ce0f59665f25e4e1d0ad04f4ea9).

## Results of G0 for S1 and S2, and of the import gate of S2o (written 2026-10-02T19:58Z, before the next trials)

Window of 19:51:19Z to 19:53:47Z; 2,599 MiB in use after the workstation's services were stopped and before the first
load; the precondition check passed before each arm; the workstation's services were active again at 19:53:47Z.

| Arm | Scored runs passed | Tool call completed | Layers on the GPU | Record |
| --- | --- | --- | --- | --- |
| S1, Bonsai PTQ1_0 on the Prism server | 0 of 3 | in 0 of 3 | 65 of 65 | raw/M11-g0-S1.txt, sha256 4849c4444e2db3596364102c8560419915fbf12e05dbfe7cd270ab9a7c2502f2 |
| S2, Swift IQ3_S on the Prism server | 0 of 3 | in 0 of 3 | 65 of 65 | raw/M11-g0-S2.txt, sha256 09046e461acbc43cb231e41fb788e613694746f34672918ada4123dde8aced2e |

- Both arms fail G0 and cannot take the slot. In every run the server's log carries the warning
  `unsupported Responses tool type 'namespace' skipped`, the client's turn completes, and no call of the time
  server's tool is recorded. It is the same finding that settled the model-server slot against stock llama.cpp.
- What this is and is not: the gate tests the server's Responses layer with the Codex client's namespaced tools. It is
  not a result about either model's tool calling through another interface. The Prism build did load the Swift file,
  so S2's load condition held.
- A correction of this session's own printed summary: its count of "HTTP 500" lines matched task numbers and token
  counters in the debug log, not HTTP statuses (raw/M13-next.txt, sha256
  e74a9f71c9ab55950bea9abd01fe2a8497d18ea35c5d96ef1e62f029c789c35e). No HTTP 500 is established by these records.
- S1b's declared condition has occurred. Its file is downloaded and matches its frozen hash (19:56:26Z) and its gate
  is prepared from the same frozen files; it runs G0 next.
- S2o's import gate passed at 19:57Z: `ollama create` exited 0 and `ollama show` lists the capabilities completion,
  tools and thinking (levels false, low, medium, xhigh; default medium), quantization IQ3_S, architecture qwen35.
  The library model file it was built from carries `RENDERER qwen3.8` and `PARSER qwen3.5`; the S2o model file's
  sha256 is 8911245e6678ee1fac043d31d20de14ea9ed3d8834ccee5beb92e726b769e8f6. S2o runs A1 next, with the script
  steps/M14-a1-ext.py (sha256 53b503f28bb3931e41d6c49dce9d482a0be88122fee6caae8bfd0af5589bd76f): the procedure of
  amendment 2 with the context in each request, the embedder's context of 8,192, and an unload at its end.

## Results of G0 for S1b and of A1 for S2o (written 2026-10-02T20:02Z)

Window of 19:58:43Z to 20:01:31Z; 2,605 MiB in use before the first load; precondition check passed before each
step; the workstation's services were active again at 20:01:31Z.

- **S1b, Bonsai PQ2_0 on the Prism server: G0 failed, 0 of 3 scored runs**, tool call completed in 0 of 3, 65 of 65
  layers on the GPU (raw/M11-g0-S1b.txt, sha256 e85547ce992b61779ad91bc399daf0e4def10ca2741da8c472179dcaa3a46587).
  With S1, both declared Bonsai arms are out by the function gate. The reason is the server's Responses layer, as
  for S1 and S2.
- **S2o, Swift IQ3_S on Ollama: A1 passed** (raw/M14-a1-swift-iq3s-s2o.txt, sha256
  88774055823167ec813f3b69b75e1bc02468d038ac5bdd84a234a314b207248a). After the long prompt (56,847 prompt tokens, the
  fixed prompt cc741c12…, 64 output tokens) the server lists the generation model with 14.81 GiB, all on the GPU, at
  a context of 64,000, and the embedder with 2.66 GiB, all on the GPU, at a context of 8,192. GPU memory in use:
  2,616 MiB before the load, 18,406 MiB with the model, 21,564 MiB with the embedder, 21,579 MiB after the long
  prompt, of 24,564 MiB. Prompt processing 2,249.6 tokens per second, output 43.1 tokens per second, load 61.5
  seconds. Everything was unloaded at the end (2,599 MiB).
- **Where the extension stands.** Out: S1 and S1b (G0), S2 (G0). In, both on the manifest's server: S2o (A1 passed
  today) and the control C (`gpt-oss:20b`, A1b passed at 18:16Z: 12.97 GiB, all on the GPU, embedder resident, 108.9
  output tokens per second). A2 decides between them under the rule as written: the higher primary share takes the
  slot, and a difference whose interval includes zero is a tie that goes to the arm with more free GPU memory at
  64,000 with the embedder resident. On today's figures that arm is C.
- Not comparable and not used for a decision: the two speeds above come from different trials of one prompt each.

## Amendment 3b: A2's materials, written 2026-10-02T20:07:43Z, before any A2 request

Arms: S2o and C, both on the measurement Ollama server (0.35.0). Part A2's cases, surfaces, metric, interval and rule
stand; this fixes the literals it left open. Setup record raw/M15-a2-setup.txt (sha256
18bd6d4b65a146c6d19138d037ea8c33aa7a32a57a88e3f7d61f2faad0a6dc9b); no model was loaded for it.

**Models as addressed.** `swift-iq3s-s2o-64k` and `gpt-oss-20b-64k`: the weights of the A1 arms with one added line in
a derived model file, `PARAMETER num_ctx 64000`. A difference from amendment 3a, declared here: 3a said the context is
sent with each request, but the OpenAI- and Anthropic-compatible surfaces cannot carry it, so the model carries it.

**Evaluation package.** Inspect AI 0.3.273 (the manifest's version) with inspect-evals 0.23.0 (released 2026-10-02,
tag commit bd59dd3b48974ad2e91219a6ceed41011e201163), task `inspect_evals/bfcl` with `-T categories=simple_python`. The
package has no category named `simple`; `simple_python` is the set the benchmark calls simple, and its Java and
JavaScript variants are not part of this test. Client libraries in the same environment: openai 3.24.0, anthropic
1.11.0, jsonschema 4.26.0.

**Cases.** `--sample-shuffle 20260927 --limit 100`, once per surface and arm. On a surface the two arms must have run
the same 100 case ids; if not, that surface's comparison is void and the decision script stops.

**Surfaces.** chat: `openai-api/ollama/<model>` against the server's `/v1`. responses: `openai/<model>` with
`-M responses_api=true` against `/v1`. messages: `anthropic/<model>` against the server's root. A surface the package
cannot address is reported as not evaluated with the reason, and the comparison uses the surfaces both arms ran.

**Request options, the same for both arms.** `--max-tokens 16384 --reasoning-effort medium --max-connections 1
--max-retries 0 --no-fail-on-error --timeout 900`. Sampling is not set: each model answers with its own parameters.

**Primary metric.** `a2_validity.py` (sha256 d67bffa8a13ac0cdc185c1ee8ae85ec1807dd2de2a9960171aa1c2b772249e7e) reads
the package's logs. A case is valid when the first model answer of the sample carries at least one tool call and
every call in it parses, names a tool offered in that request and has arguments that satisfy that tool's JSON
schema. A request that errored and an answer without a tool call are invalid. The package's own score (its match
against the expected call) is recorded beside it and decides nothing.

**Decision statistic.** `a2_bootstrap.py` (sha256 d69c4df08cd47164a65e227ebe11dddba203911ae492c7eb1462fae0d20f369a):
the difference of the two shares over all cases and surfaces both arms ran, resampled over case ids. Rule as written:
the higher share takes the slot; an interval that includes zero is a tie, which goes to the arm with more free GPU
memory at 64,000 with the embedder resident; an arm with no valid tool call at all fails.

**Client part, recorded and not deciding.** `a2_tasks.py` (sha256
3900efc4a269ad0c790ed3bac6861f622e338290bf115bcb4d73054db81c1071) holds five tasks with their starting files, fixed
prompts and fixed file checks: T1 create a file, T2 edit a file, T3 run a command and write its output, T4 read a
file and answer, T5 a two-step edit that depends on a command's output. Control, run before this hash: every check
fails on the starting repository and passes after the intended change. `a2_run_client.sh` (sha256
0d6fa4f3e350f560d19675c03ee0fb809b1b50b0373b35ffec572c877246d4b4) runs one task once in a fresh repository with an
emptied environment and a scratch home, wall limit 900 seconds: Codex 0.160.0 as
`codex exec --oss --local-provider ollama -m <model> --sandbox workspace-write --skip-git-repo-check --json` with
effort `medium`; Claude Code 2.1.287 as `ollama launch claude --model <model> --yes -- -p <prompt> --permission-mode
bypassPermissions --output-format json`. The bfcl runner is `a2_run_bfcl.sh` (sha256
25665689d61bf3c882a3790a1a4fa4adde60c718c15b36d6a4823ef74d719767). Every runner refuses a label that exists.

**Pilot, unscored.** Before the scored runs: cases 101 to 103 of the same shuffle (outside the 100), once per surface
with S2o, and an extra task P0 (create a one-line file) once per client with S2o. Its only purposes are to show that
each command reaches the server and to time a case. Its outputs enter no metric. It may lead to exactly two kinds of
change, each recorded as a deviation with the diff: a command that does not reach the server because of a wrong
option or address is corrected; a surface the package cannot address is marked not evaluated. It may not change the
cases, the limits, the effort, the metric or the rule.

**Order and windows.** One arm and one surface per step: S2o chat, C chat, S2o responses, C responses, S2o messages, C
messages, then the client tasks for S2o and for C. The server holds no model before each step (the precondition
check of deviation 1). GPU memory before and after each run is recorded. A step is not started when it could
outlive its window; it runs in the next one. No decision is taken before every step has run.

## Pilot outcome and deviation 2, written 2026-10-02T20:11:43Z, before any scored A2 run

Pilot window 20:08:43Z to 20:10:40Z, unscored, Swift arm only; the workstation's services were active again at
20:10:40Z. Records and hashes: raw/A2-bfcl-pilot-s2o-chat.txt 060559a3…a201, -responses.txt e9f7f250…484c,
-messages.txt 5747687c…cc09, raw/A2-client-pilot-codex-P0.txt fefb4f4d…6d64, -claude-P0.txt c71a2248…d5d7,
raw/M16-pilot-errors.txt e20c1abf…7493 (full values in the lane's hash list).

- **chat and responses reach the server and return scored samples** (three held-out cases each, 25 and 20 seconds
  including the model load). The scored runs on these two surfaces go ahead as frozen.
- **messages is not evaluated through the package**, for both arms. The request reaches the server and is answered,
  but Inspect AI 0.3.273's Anthropic provider cannot read the answer of this thinking model: every sample stops with
  `1 validation error for ContentReasoning: reasoning: Input should be a valid string [...] input_value=None`. That is
  the case Part A2 names (a surface the package cannot address). Turning thinking off would change the effort, which
  the pilot may not do. The comparison uses chat and responses. The Messages route is still exercised by the real
  client in the client part: Claude Code through the server's launch entry completed the pilot task (2 turns, 20.9
  seconds, file check passed).
- **Deviation 2, the Codex client command.** With `-m swift-iq3s-s2o-64k` Codex's local-provider setup did not find
  the model, tried to pull it from the registry and stopped (`OSS setup failed: Pull failed: pull model manifest: file
  does not exist`); the server lists the model as `swift-iq3s-s2o-64k:latest`. This is a command that does not reach
  the server for a model request because of a wrong option, one of the two changes the pilot may lead to. The runner
  now passes the name with its tag to Codex only (three added lines and one changed word in `a2_run_client.sh`; new
  sha256 875530525864880c50e88596a53618fb64b21d3f5e64b4bd95068325b7830260, the frozen one was 0d6fa4f3…d4b4). The same
  pilot task runs once more for Codex, unscored, under the label `pilot2`, before the client part.
- Timing for the windows: about 6 to 8 seconds per case, so a scored run of 100 cases takes about a quarter of an
  hour. Nothing else changes: cases, limits, effort, metric and rule are as frozen.

## Results of A2's scored runs, and deviation 3 (written 2026-10-02T20:34:21Z)

**Scored runs, window of 20:12:02Z to 20:26:57Z** (one unscored repeat of the Codex pilot task first: passed with the
corrected command). Both arms ran the same 100 case ids on both surfaces; no sample errored.

| Run | First-pass valid tool calls | The package's own score | Record (raw/…) sha256 |
| --- | --- | --- | --- |
| S2o, chat | 100 of 100 | 97 correct | A2-bfcl-s2o-chat.txt 73bfea42c9a82b43ba6bb09937cab64faed4570c24c42e94ad258c501562d47a |
| C, chat | 87 of 100 | 83 correct | A2-bfcl-c-chat.txt 627565698cb5b28ebe597f93e8de4b909767be4e0e39c7c8b97ee40d232dc5e7 |
| S2o, responses | 100 of 100 | 95 correct | A2-bfcl-s2o-responses.txt 5db580e8ae05efce13bf6543785fcf84f4be8c232bb35dc31c416461c8a91bf9 |
| C, responses | 88 of 100 | 83 correct | A2-bfcl-c-responses.txt f4b22a63bf27f17b0e9822277fe12305627fcb44ef04f423b2434a39230d9974 |

Decision statistic (raw/M18-bootstrap.txt, sha256 3fe228c28e2ca7440989ad554507af6e212ef144f2136b64f48b3c56bc1f5c9f):
shares 1.000 for S2o and 0.875 for C over 200 case-surface pairs each; difference 0.125; 95% paired bootstrap
interval over cases 0.065 to 0.19 (10,000 resamples, seed 20260927). The interval excludes zero: not a tie.

C's invalid cases, read after the statistic: on chat 9 with arguments outside a fixed set of allowed values (for
example `pop` where the schema allows `Pop`) and 4 without a tool call; on responses 9 and 3. They are judged as the
frozen definition says; the definition was not changed. GPU memory with the model resident during the runs: 18.6 to
18.7 GB in use for S2o, 17.1 GB for C, of 24.6 GB, with 2.2 to 2.9 GB held by Windows before each load.

**Client part, window of 20:29:13Z to 20:33:44Z.** S2o: Codex passed T1 to T5 (12 to 17 seconds each) and Claude Code
passed T1 to T5 (19 to 24 seconds each); ten of ten file checks pass. The ten run records are intact inside the
measurement distribution (their hashes: raw/A2-client-scored-s2o-hashes.txt, sha256
b0d13a49c3e4ec78a565f695c28279a7dcae337fa9447fecea9637caeac59ab2).

**Deviation 3, this session's error.** The window gave both arms the same label. The runner refuses a label that
exists, so C's ten client runs were refused within seconds and never started; and the window script wrote those
refusal lines over the workstation-side copies of S2o's ten records, whose names did not carry the model. Nothing was
lost inside the distribution, and no result of C's client tasks exists yet, so nothing was chosen on an outcome.
Handling: C's ten tasks run once under the label `scored-c`; the window script now names a record after the model
too and never writes over a record that exists. The ten overwritten copies are kept as they are, as the record of
the refusals.

No decision is written before C's client tasks have run.

## Result of Part A (written 2026-10-02T20:38:53Z)

**C's client tasks, window of 20:34:59Z to 20:38:22Z, label `scored-c`:** Codex passed T1 to T5 (11 to 21 seconds
each) and Claude Code passed T1 to T5 (12 to 20 seconds each); ten of ten file checks pass (hash list
raw/A2-client-scored-c-hashes.txt, sha256 e53dcfed7352ad0dfba7393e9536449687d13e76ef002228ea5e6941a6055277). Every
step of A2 has now run.

**Decision by the rules as written.** The generation slot goes to **S2o: Swift-1.5-Qwen3.8-27B, IQ3_S (file sha256
1333c6ea…a786 at revision d74895bb), served by Ollama 0.35.0** through a model file that takes the library
qwen3.8:27b model's renderer, parser and parameters and adds a context of 64,000.

| Rule | S2o | C (gpt-oss:20b) |
| --- | --- | --- |
| G0, function gate | not applicable: the manifest's server | not applicable |
| A1, co-residency in the order of use under condition N | passes: 14.81 GiB all on the GPU, embedder 2.66 GiB all on the GPU | passes (A1b, 18:16Z): 12.97 GiB all on the GPU, embedder resident |
| A2 primary, first-pass valid tool calls over chat and responses | 200 of 200 | 175 of 200 |
| A2 decision statistic | difference 0.125, interval 0.065 to 0.19: not a tie | |
| Second-server rule | does not apply: one server | does not apply |
| Recorded, not deciding: the package's own score | 97 and 95 of 100 | 83 and 83 of 100 |
| Recorded, not deciding: client tasks, Codex and Claude Code | 10 of 10 | 10 of 10 |
| Recorded, not deciding: seconds for 100 cases (chat, responses) | 292, 303 | 100, 139 |

Out before A2: S1 and S1b (Bonsai, both packings) and S2 (Swift on the Prism server), each 0 of 3 at G0 because the
Prism server's Responses layer skips the Codex client's namespaced tools; `qwen3.8:27b` (not fully on the GPU at
64,000).

**What this result does not establish, and what a reader should weigh.**

- It is a result about first-pass tool-call validity on one public set of 100 simple cases on two interfaces, on one
  workstation, one run per case. It says nothing about coding quality, long tasks, throughput under concurrent
  requests or behaviour above 64,000 tokens.
- The Anthropic-style interface was not measured through the evaluation package (deviation at the pilot); it was
  exercised only by Claude Code in the client tasks, which both arms passed.
- S2o is slower in these runs: about three times the control's time for the same 100 cases, and 43 against about 108
  output tokens per second on single long prompts that were not run as a speed comparison.
- S2o leaves less memory free: with the embedder resident it used 21,579 of 24,564 MiB while Windows held about
  2,600 MiB. Earlier the same day Windows held up to about 5,900 MiB; at that level the same load would leave under
  one GB. Co-residency on a busier desktop is not measured.
- The import into Ollama is this lane's system, not a route the publisher documents; the publisher's own route
  (llama.cpp's server) failed G0 here for a reason that lies in that server. The quantization's own card says its
  quality tests used a 512-token context and do not establish quality at long contexts.
- The file's licence is the publisher's own (Swift Open License v1.0, with Qwen's parts under Apache-2.0). It is
  recorded, not judged.
- Three deviations are recorded above (a void first window, the Codex client's model name, a reused label). None
  changed a case, a limit, the metric or the rule, and none was decided on an outcome.

**What happens next.** Part B (embedding and reranking) runs with this generation model resident, after its own
amendment with the Codex lane's retrieval arms. The manifest row changes only in a pull request that carries this
document, the hashes of the raw records and the compact result, and that the other model family has read.

## Amendment 4: Part B freeze sheet, written 2026-10-02T22:48:48Z, before any download of an arm's weights

Sources: the other lane's retrieval proposal (`CODEX-LOCAL-RETRIEVAL-COMPARISON-PREPARATION-20261002.md`); a literal
extraction of the four model cards, MTEB 2.22.1, sentence-transformers 6.1.0 and Ollama 0.35.0 at pinned commits
(record sha256 aec1c244aa5a866049c0c2df9a47f0e0fb9239aa8f0abf774bc98ed82cd29f3c, kept in the lane's state); the task
loaded in the measurement environment (raw/M20-partb-task.txt, sha256
c5f571f181f514e56923d40e7b3ea8bb795ad03087895fe2be013b24fc6e3fc7). Part B's set, metric, interval and rules as written
above stand; this fixes the literals and adds the arms.

### Environment (installed 22:06Z to 22:07Z, no model loaded)

A separate virtual environment in the measurement distribution: MTEB 2.22.1 (tag commit 79857d39), sentence-transformers
6.1.0, transformers 5.18.0, torch 2.14.1 (CUDA 13.0; the RTX 4090 is visible), datasets 5.0.1, pytrec-eval-terrier
0.5.10, numpy 2.5.3 (freeze list sha256 386ad348b1643ec653cc893bbb5b2db89310522f2601d1ff335c39e04581f642). Before the
first run of E4 the extras MTEB declares for it are added (`qwen-vl-utils>=0.0.14`, `accelerate>=1.1.0`) and the
freeze list is recorded again.

### Task, fixed

`CQADupstackUnixRetrieval`, dataset `mteb/cqadupstack-unix` at revision
`6c6430d3a6d36f8d2a829195bc5dc94d7e063e53`, split `test`: 47,382 documents, 1,072 queries, 1,693 relevance
judgements. No chunking. The task carries no prompt of its own.

### Arms of the embedding condition (this condition decides the slot)

| Arm | System | How MTEB calls it |
| --- | --- | --- |
| E1 | `qwen3-embedding:0.6b` on Ollama 0.35.0 (library manifest `ac6da0df…`, Q8_0 GGUF), as the derived model `qwen3-embedding-8k` (the same weights with `PARAMETER num_ctx 8192`, amendment 3a) | MTEB's own `OpenAIAPIEncodeWrapper` against `http://127.0.0.1:21434` (`/v1/embeddings`), `use_chat_template=False`, `modalities=["text"]`, `use_instructions=True`, `instruction_template` = MTEB's own Qwen3-Embedding template (`mteb/models/model_implementations/qwen3_models.py`, lines 13 to 23), `apply_instruction_to_documents=False`. For this task the query prefix is therefore `Instruct: Retrieve text based on user query.\nQuery:` and documents have none, as MTEB evaluates the reference model |
| E2 | `embeddinggemma` (`:latest` = `:300m`, manifest `85462619…`, BF16 GGUF, its own `num_ctx` 2048) on the same server | the same wrapper with `use_instructions=False` and `prompt_dict={"Retrieval-query": "task: search result \| query: ", "Retrieval-document": "title: none \| text: "}`, the prompts MTEB uses for the reference model |
| E3 | `nvidia/Nemotron-3-Embed-1B-BF16` at MTEB's registered revision `f880174635613cff04033875fc6a69296cb72006`, in the evaluation process (a second model server in the sense of Part B) | `mteb.get_model` with its registered loader (sentence-transformers, `processor_kwargs={"model_max_length": 4096}`; built-in prompts `query: ` and `passage: `) |
| E4 | `tencent/WeMM-Embedding-2B` at MTEB's registered revision `df8094e5caf29083d9cac28e96fad6cfbe3ee57f`, in the evaluation process (a second model server) | `mteb.get_model` with its registered `WeMMEncoderWrapper` (`trust_remote_code=True`) |

Revisions: MTEB refuses a revision other than the registered one for a registered name. The extraction compared both
trees with the card heads the other lane reviewed: for E3 and E4 only `README.md` differs, every weight and code file
is byte-identical, so the registered revision runs the reviewed weights. Weight files, checked against these hashes
after download: E3 `model.safetensors` 2,281,852,472 bytes, sha256
`f959c3b04e66b42de280bfb97c140cb7e0bfe25e3ecb0b4464c68a8436b2d04f`; E4 `model.safetensors` 5,441,695,216 bytes,
sha256 `e1a1ad752808c26965aa97d37bf4a9bca71d838513f41e83790cb1e71cac6e59`. Licences, recorded only: E1 Apache-2.0 (Qwen),
E2 Gemma terms, E3 OpenMDW 1.1 with Apache-2.0 parts, E4 Apache-2.0 with third-party notices.

The two Ollama arms are what the manifest's single model server would serve; the GGUF files may differ in quality
from the reference weights, and the record says so rather than attributing a difference to the model alone.

### Conditions

- Condition N of amendment 1 and the precondition check of deviation 1 before every load.
- The generation model `swift-iq3s-s2o-64k` is loaded first (a short prompt, context 64,000, keep-alive unlimited) and
  stays resident during every embedding run; it is checked after each run.
- One arm at a time; between arms the previous embedder is unloaded (Ollama) or its process has exited (E3, E4).
- Batch size 16 for every arm (`encode_kwargs={"batch_size": 16}`; for E1 and E2 it is the request batch).
- Predictions are saved (`prediction_folder`), at MTEB's default top 1,000 per query.

### Gates

- **F (fit), for E3 and E4:** with the generation model resident, the arm is loaded on the GPU and encodes the first
  256 documents of the corpus at batch size 16. It passes when no out-of-memory error occurs and the generation model
  is still listed with all of its size on the GPU afterwards. An arm that fails is recorded as `does not fit beside the
  generation model` and is out, as Part B says. No quantization or other format is substituted to make it fit.
- **C (consistency), for every arm:** the mean of the per-query nDCG@10 values computed from the saved predictions with
  pytrec_eval equals MTEB's reported `ndcg_at_10` within 1e-6. An arm whose record fails this is reported as invalid,
  with the reason.

### Metric, interval and decision

Per-query nDCG@10 over the 1,072 queries (a query without a relevant document in the top 10 scores 0). Paired bootstrap
over queries, 10,000 resamples, seed 20260927. Rules as written in Part B: between E1 and E2 the higher nDCG@10 takes
the slot, and a difference whose interval includes zero is a tie that goes to the arm with the smaller resident GPU
memory (Ollama's reported size of the embedder); E3 or E4 takes the slot only if it passed F and its difference to that
single-server winner has an interval entirely above zero. Recorded, not deciding: seconds to encode the corpus, resident
memory, MTEB's other retrieval scores.

### The reranking condition the other lane proposed: not run in this round

Two reasons, written before any result: the manifest row `reranker-model` is resolved as not installed because no
installed retrieval owner can call an external reranker (QMD reranks in-process with its bundled model), so no result
of this condition could change an install; and `zerank-2` (7.49 GiB of weights) cannot be resident beside the
generation model on this card. It runs, with frozen first-stage candidates from the embedding winner, when an owner
that can call an external reranker is installed. This is recorded as a disagreement with the proposal, not as its
acceptance; the other lane may object before the first Part B run.

### Scripts (hashed before the first run, in the lane's measurement folder)

`partb_run.py` builds each arm exactly as above and calls `mteb.evaluate` with the prediction folder and a result
cache per arm; `partb_fit.py` runs gate F; `partb_perquery.py` computes per-query nDCG@10 and gate C;
`partb_bootstrap.py` computes the decision statistic. They are reviewed against this text before the first run, and
their hashes are appended here as amendment 4a.

## Amendment 4a, written 2026-10-02T23:12:42Z, before any model of Part B is loaded

An independent read of the scripts against amendment 4 (Opus, read-only, against the installed MTEB 2.22.1 source)
found two blocking defects and four defects; two of them were in this text, not only in the code. Each is corrected
here, before any load; nothing was run on a model in between. Downloads of E3 and E4 had happened after amendment 4 and
are unaffected (both hashes matched).

1. **B1, prompts of E1 and E2.** As written in the table of amendment 4, MTEB's wrapper would have sent no prompt at
   all: it takes its instruction branch only when `prompt_dict` is set (`mteb/models/openai_wrappers.py`, lines 766 to
   772), and it looks a prompt name up in `model_prompts`, which it never sets (`mteb/models/abs_encoder.py`, lines 57,
   82 and 408). Corrected construction: E1 adds `prompt_dict={}`; E2 also sets `model_prompts` to the same two entries
   as `prompt_dict`. Observed with a stub instead of the server's embedding call (record raw/PB-selftests.txt, sha256
   f266cfea14e509274ef1034f6fd9ea4939232ec8c7f29bb42c5064f24b5f4fe2): E1 sends `Instruct: Retrieve text based on user
   query.\nQuery:` before each query and nothing before documents; E2 sends `task: search result | query: ` before
   queries and `title: none | text: ` before documents. These are the prompts amendment 4 intended.
2. **B2, gate C's tolerance.** MTEB reports nDCG@10 rounded to five decimals (`mteb/_evaluators/retrieval_metrics.py`,
   line 508), so "within 1e-6" would fail most valid arms. Gate C is now: the mean of the per-query values, rounded to
   five decimals, equals the reported value. Checked on a synthetic run whose reference value comes from MTEB's own
   `calculate_retrieval_scores` (0.15738, mean 0.1573763…): passes; the same run with a misreported score fails.
3. **D1, gate F on the CPU.** E3 and E4 are now built with `device="cuda"`, and gate F passes only when every parameter
   of the arm is on CUDA and torch allocated GPU memory.
4. **D2, gate F's batch size.** Gate F now passes `batch_size=16` to the encoder.
5. **D3, failures without a record.** `partb_run.py` writes its record in every case, a failure before or after the run
   included; host paths in error texts are written with `~`.
6. **D4, unloading and residency.** Both scripts refuse to start unless the generation model is the only model the
   measurement server lists and is entirely on the GPU; `partb_run.py` unloads E1 or E2 after its run and records the
   server's list before and after, and whether the generation model is still entirely on the GPU.
7. **Gate F's outcomes** (review note N2): exit 0 passes; exit 1 means does not fit (out of memory, or the generation
   model left the GPU); exit 2 means another error, which is not a fit result and does not remove the arm by itself: it
   is recorded and the arm is not run in that window.
8. **An arm that passes F and runs out of memory in the full run** (review note N3) is recorded as `does not fit beside
   the generation model` and is out, like a failed gate F.
9. **Time** (review note N4): MTEB's own `evaluation_time` and the wall time are recorded; neither decides, and the
   wall time is not comparable across the two kinds of arm.
10. **Provenance** (review note N5): each record carries the package versions, the wrapper and its prompt settings,
    the Ollama digests for E1 and E2, and MTEB's own log.
11. **The bootstrap** (review note N6) takes named arguments, challenger minus baseline, and refuses a run that failed
    gate C.

Hashes of the scripts that run, taken now:

| File | sha256 |
| --- | --- |
| partb_arms.py | f4ac3a7ef4d004955c1da0958347d2916f5b42d531deae96ba2ff2754edcff04 |
| partb_run.py | e381a73d941b851ec7fcecc2ef092ff19c9714b7e7c08f3f82ea4eeb16dd4a00 |
| partb_fit.py | 2870ee1e17b03d6d65b142774746923c4504909bc86a33eb2173ee71bf42d965 |
| partb_perquery.py | 088b62f60c0bc7283d8218a38d7b4641a1ee96a809077dafe70a1f9522b56b91 |
| partb_bootstrap.py | 3b02d65098646d2aa38cfd39a2fc2a48d31c0858fd2727d282e61b9e683cc5a4 |
| selftest_perquery.py | ebe43ecb97cd066b7d1d5a008668a940c597b8cc0cc3321d3acf349b7ab324f4 |
| selftest_prompts.py | 23a0499cba72e25d66baa055c2ef469d38621f7227f6185658b492af42177a37 |
| steps/W-partb-window.sh (the window) | 688722f71db08f360119388f0d5309f8f52075672d4fc466c9fee66f3d65ba29 |

Order of the window: E1, E2, then E3 (gate F, then its run if F passes), then E4 the same way; the bootstrap runs after
the window, on records alone.

## Window pb1 and deviation 4, written 2026-10-02T23:48:29Z, before window pb2

Window pb1, 23:13:16Z to 23:47:28Z. The precondition held; after the workstation's services stopped, Windows held
4,407 MiB (more than the 2.2 to 2.9 GB earlier today; condition N records it, it is not a pass criterion); the
generation model loaded first and stayed entirely on the GPU through every step; the workstation's services were active
again at 23:47:28Z.

| Arm | Outcome | nDCG@10 (MTEB) | Gate C | Record (raw/…) sha256 |
| --- | --- | --- | --- | --- |
| E1 qwen3-embedding-8k on Ollama | completed, 1,166 s of evaluation | 0.49827 | passes (per-query mean 0.4982736) | PB-run-E1-pb1.txt 624099446a5f11e77bfc74a7e55da352b28bf23e1fdaa6b987662eb415e3cfd9 |
| E2 embeddinggemma on Ollama | completed, 771 s | 0.41394 | passes (0.4139431) | PB-run-E2-pb1.txt d3bf67d2358f3d3b888b29ea4489164e3b8161bc4d7ec14d1c421724e04a0e3a |
| E3 Nemotron-3-Embed-1B | gate F exit 2: `RuntimeError: Failed to find C compiler` from triton while compiling a kernel; the model had loaded on CUDA | none | none | PB-fit-E3-pb1.txt 0197972b8906053d88ae8610a2a574b9ef4e8b9b584a1060f413fff8263a98ca |
| E4 WeMM-Embedding-2B | gate F exit 2: `ImportError: … missing required dependencies: torchvision … pip install mteb[wemm,image]` before loading | none | none | PB-fit-E4-pb1.txt 835a08bc97d5b807b9cccc1ff6619f1eef48ab728189d084327e665e7df4ddac |

Resident sizes reported by the server: E1 2,857,191,341 bytes, E2 681,417,113 bytes, the generation model 15,897,985,023
bytes, each entirely on the GPU.

**Deviation 4.** Both gate F errors are setup errors, not fit results; by item 7 of amendment 4a neither arm is removed,
and neither ran in pb1. The window script printed "out: gate F failed" for both, which contradicts item 7; the records
are what counts, and the script now tells exit 1 (does not fit) apart from exit 2 (sha256 now
43254cf88c50540c6725148b03fcdc25e5373938a70516910775b0e9041783e2). Two additions to the environment, exactly what the
errors named, nothing else (raw/M22-partb-env-fix.txt, sha256
4d7d4a84f3b4dd53a177f64286d7367e0b19f6561129af8a42d9478e1b64188e): Ubuntu's `build-essential` (gcc 15.2.0) so that
triton 3.8.0 can compile its kernels, and torchvision 0.29.1 for torch 2.14.1 (MTEB's `image` extra). Freeze list
sha256 abb65df4d9b889eb97a63a3dee3c1d7e2cf889bfc2500de70ef3812ccfeb4fc7. E3 and E4 run gate F and, where it passes,
their runs in window pb2, under the same rules. E1 and E2 are not rerun.

## Window pb2 and the result of Part B (written 2026-10-03T00:03:17Z)

Window pb2, 23:48:48Z to 23:59:51Z. The precondition held before any load; after the workstation's services stopped,
Windows held 4,046 MiB; the generation model loaded first (19,856 MiB in use afterwards); the workstation's services
were active again at 23:59:51Z.

| Arm | Gate F | Run | nDCG@10 (MTEB) | Gate C | Records (raw/…) sha256 |
| --- | --- | --- | --- | --- | --- |
| E3 Nemotron-3-Embed-1B | exit 0: no out-of-memory error, parameters on CUDA, torch peak 9,160,205,824 bytes, the generation model listed entirely on the GPU afterwards | completed, 460 s of evaluation, torch peak 10,616,148,992 bytes | 0.5014 | passes (per-query mean 0.5013977) | PB-fit-E3-pb2.txt f672d445672d6cb959f54812f79e020c85ba239ec3bc7f071556f593447b2348; PB-run-E3-pb2.txt 5d48656c29199cb5d1330eab61da3ac69e7ca062ddbd49715b77d9f34080cc71 |
| E4 WeMM-Embedding-2B | exit 0: torch peak 13,006,749,184 bytes | out of memory in the full run after 47.5 s, torch peak 15,978,033,152 bytes; no predictions | none | none | PB-fit-E4-pb2.txt 51eb9faf46f3c47df6f47ddafe67252dd42da504fccc3468e5dd94ae05c98906; PB-run-E4-pb2.txt 74149e3c90effbeb4788bda09e013c40dae8973b77aa3489c116dcd517e36971 |

**E4 is out.** By item 8 of amendment 4a, an arm that passes F and runs out of memory in the full run is recorded as
`does not fit beside the generation model`. The record's `status` reads "failed before or after the run": after the
evaluation had failed with `out_of_memory: true`, the script's memory query (`torch.cuda.mem_get_info`, partb_run.py
line 56) raised the same sticky CUDA out-of-memory error, and the outer handler replaced the evaluation's error text
with that traceback. The outcome is not in doubt, since only the evaluation's handler sets `out_of_memory`; losing the
first error text is a defect of the recording, noted here and to be fixed before the script is used again. MTEB logged
that `chunk_gated_delta_rule` fell back to its reference PyTorch implementation because `flash-linear-attention` is not
installed. MTEB does not declare that package for this model, and nothing was added to make the arm fit (amendment 4:
no substitution).

**Decision statistic**, on records alone, 2026-10-03T00:01:16Z to 00:01:28Z (raw/PB-bootstrap.txt, sha256
3715a13234ad46aa150dcebdfd1930c638998e73cd31c5319f473a5b09bf1302; step steps/M23-partb-bootstrap.sh, sha256
88d836d9b81efaaf179b5f04b7cbd78592db4b7dd9d50c223ac7a60b3adb934d; partb_bootstrap.py as hashed in amendment 4a; 1,072
queries, 10,000 resamples, seed 20260927):

| Comparison | Difference | 95% interval | Reading by the rule |
| --- | --- | --- | --- |
| E1 minus E2 | 0.084331 | [0.067738, 0.100656] | not a tie: E1 is the single-server winner |
| E3 minus E1 | 0.003124 | [-0.012194, 0.018141] | the interval includes zero: E3 does not take the slot |
| E3 minus E2 (recorded, not deciding) | 0.087455 | [0.072733, 0.102348] | none |

**Result of Part B.** By the rule fixed before any run, the embedding slot goes to E1: `qwen3-embedding:0.6b` (Q8_0)
on Ollama 0.35.0 as the derived model `qwen3-embedding-8k` (`num_ctx` 8192), nDCG@10 0.49827 on
CQADupstackUnixRetrieval, measured with the generation model `swift-iq3s-s2o-64k` resident. Both local-model slots are
then served by the one Ollama server. The manifest rows change only after the other lane's read.

**An observation that limits what gate F shows (recorded, not deciding).** In pb2 the GPU memory in use fell between
steps while Ollama kept listing the generation model (15,897,985,023 bytes) with all of its size on the GPU: 19,856 MiB
after it loaded, 23,722 MiB after E3's gate F, then 13,021 MiB before E3's run, 10,980 MiB before E4's gate F, 8,269 MiB
before E4's run and 1,906 MiB at the end of the window. These readings are consistent with Windows moving part of the
generation model's memory off the card while the in-process arms allocated (under WSL the Windows driver manages GPU
memory); gate F reads the server's listing and cannot see that. "E3 passes F" therefore means it passes the frozen
criterion, not that co-residency is shown. In pb1 the readings matched the resident models (20,210 MiB before E1's run
and 23,029 MiB after it, with E1's 2,857,191,341 bytes loaded), so E1's co-residency with the generation model is
supported by both readings. The decision does not depend on this: E3 tied and E4 ran out of memory. For any later fit
test on this host: compare the card's used memory with the sum of the resident models and time one fixed generation
request before and after, instead of reading the server's listing alone.

**Limits.** One public retrieval task (Unix questions from StackExchange), one workstation, one run per arm; E1's and
E2's prompts as observed in amendment 4a; Nemotron's tie holds for this task only; the reranking condition was not run
(amendment 4). Recorded, not deciding: evaluation time E1 1,166 s, E2 771 s, E3 460 s (in-process, not comparable with
the Ollama arms).
