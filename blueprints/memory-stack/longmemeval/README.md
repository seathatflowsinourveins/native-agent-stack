# LongMemEval-S retrieval harness: the Mac run's code and protocol

This directory holds, byte-exact, the preregistration, harness, summarizer, launch scripts, frozen
question manifest and agentmemory lock behind the Mac LongMemEval-S retrieval run of 2026-09-24
and 25. They are committed for host request
[#274](https://github.com/seathatflowsinourveins/native-agent-stack/issues/274), so that the
workstation (`nativestack-5975wx-20260925`) can draft amendment A17 and run the confirmatory
rerun against files in Git. The Mac measurements are recorded in
[`evidence/artifacts/memory-stack-20260925/convergence.json`](../../../evidence/artifacts/memory-stack-20260925/convergence.json),
which lists this preregistration (sha256 `1f3ca9d5…`) as "Not committed".

- **Nothing was run for this commit.** No arm, model or embedding server ran. The Mac results
  stay descriptive under amendment A15.2; confirmatory decisions need the rerun.
- **The copied files are frozen.** Every file in `SHA256SUMS` except `README.md` and `.gitignore`
  is a record. A17, a harness v4 or any fix lands as a new file. An edit here breaks the pinned
  hashes that #274 is accepted against.
- **Three placement changes.** The npm files are stored as `agentmemory/*.frozen`, for the reason
  given in [Restoring the agentmemory install](#restoring-the-agentmemory-install). The Mac launch
  scripts are in `mac-drivers/`. Two harness revisions that no longer exist as files on the Mac
  are in `reconstructed/`.

## Files

Times are EDT. "Mac run directory" means `$HOME/.local/share/agent-ecosystem/bench/longmemeval/`
on the coordinator Mac, and "bench directory" its parent.

| File | sha256 | Bytes | Source | Role |
| --- | --- | --- | --- | --- |
| `PREREGISTRATION.md` | `1f3ca9d554cff24dc785c35f275335027a831dd386f460890f8a3082a07c11c2` | 33,527 | agent-ecosystem commit `2c3e09bbec19`, `evals/longmemeval/PREREGISTRATION.md` (blob `f5c475db`) | protocol with amendments A1–A16 (no A16.1 or later) |
| `eligible-manifest.json` | `871f5da108b2901204aa01315b87d91cdee8d4e61dea96f4499916cbc19a05b7` | 13,607 | Mac run directory, written 2026-09-24 18:47 | the frozen denominator (A1): the dataset sha256 and 419 official-track and 470 full-session-track question ids; no final newline |
| `lme_harness.py` | `b59ee6f5ada7392e4c250ad54dd1ec75e2e30921bca8ae4265807f587716f751` | 31,991 | Mac run directory, last edited 21:52 | harness v3 (A1–A12), the runner |
| `lme_harness.v2.py` | `38dbb42ff0403f76104d44d04b5cb30ec0cf753107a17799107bd876b157f7c3` | 29,897 | Mac run directory | harness v2 (A1–A10) |
| `lme_harness.v1.py` | `1f9c4f5d48680410c602b1002c78e610c5c3893f210f4d647ceaacb8c668348b` | 25,976 | Mac run directory, the copy A10 keeps | harness v1 including the A8 arms-table entries |
| `reconstructed/lme_harness.v1a.py` | `09940d85d144d9b4bd58610dfb11f3d1c579ce544f9562fdc6ea137b5a4c9e57` | 25,416 | rebuilt, see below | harness v1 as B1, B2 and D1 loaded it, before the A8 entries |
| `reconstructed/lme_harness.v3pre.py` | `15b4fe3e2d01ae990c7aabbce9b929ececae8dd0697c9207782816215c11d5ec` | 31,422 | recovered, see below | harness with A11 but not A12 |
| `lme_summarize.py` | `244fa443a392d366a88890f5dc25a1004665af864a28260d6b018c7d55479d42` | 18,683 | Mac run directory | summarizer v3 (A1–A14); imports `lme_harness.py` from its own directory |
| `embed_cache_proxy.py` | `13621039cfaf1a3865307083fbd0124c0617c7401169b729f66c022b2c21a202` | 6,751 | Mac run directory | A13 byte-exact embedding cache, standard library only |
| `run_official_oracle.py` | `fc2c4e2e88032412a37cabf1dadace1c0e4e54265e65fa0374f9545e60e1ad67` | 472 | Mac run directory | A1 oracle shim for a host without CUDA |
| `mac-drivers/run_queue.sh` | `f73ea87b5b098e6075c2caa0aa8434eb6dfdd70b07ffbf9ba701afe8ae56c655` | 5,289 | bench directory | A13 GPU queue; it ran C3 rows 32–348 |
| `mac-drivers/run_c3_resume.sh` | `01051987ddbdb3c870aab31bc7a3b20baf540f9625a309ac6f1dca26ddd07cdd` | 2,791 | bench directory | post-reboot resume: C3 rows 349–470 and the drift check |
| `mac-drivers/run_d3.sh` | `20e0dfdb3ab975f39a994b98d86f9da69282f15b080dd684a2baee9021ad9aaa` | 1,303 | Mac run directory | the slot smoke test, then D3 (12 rows, excluded by A15.2) |
| `agentmemory/package-lock.json.frozen` | `e45aa62e9a2b6897e7024d138945b5c5a3bcc50f2e0d1ba548ecc5b6a73c8a27` | 114,313 | `package-lock.json` in the bench directory's `agentmemory/` install prefix, written 2026-09-24 18:42 and never modified | npm lockfile v3: `@agentmemory/agentmemory` 0.9.29, `iii-sdk` 0.11.2 |
| `agentmemory/package.json.frozen` | `f735eef9db3d00f08dcacf74d5057a5a662d620856fce836ca1ad07ac67ec76e` | 113 | `package.json` of the same prefix | pins `@agentmemory/agentmemory` 0.9.29 |

`README.md`, `.gitignore` and `SHA256SUMS` were written for this commit. `.gitignore` keeps a run's
`data`, `models`, `cache`, `logs`, `official-logs` and `results*` directories (or symlinks to
them) and its reports out of Git, because the harness and the summarizer resolve those paths next
to themselves.

## Which code produced which arm

Result rows carry no harness version. This mapping comes from a read-only reconstruction on
2026-09-25 that used log timings, row schemas, file times, bytecode headers and the coordinator
session's edit history.

| Arm | Code that ran | Here |
| --- | --- | --- |
| A0 official `flat-bm25` | the official `run_retrieval.py` at `9e0b455`, run directly with `--retriever flat-bm25 --granularity session` (18:55) | none: upstream code |
| A1 official oracle | `run_official_oracle.py` around the official runner (18:56) | `run_official_oracle.py` |
| A1b full-session oracle | computed by the summarizer (`full_oracle_rows`) | `lme_summarize.py` |
| B1 `bm25-full`, B2 `dense-qwen3`, D1 `am-keyless`, and the C1 limit-10 sensitivity run | harness v1 as loaded at 18:55–18:57 (`09940d85…`) | `reconstructed/lme_harness.v1a.py` |
| C1 `aimem-fts` (limit 50), C2 `aimem-minilm`, D2 `am-minilm` | harness v2 (`38dbb42f…`), launched at 20:32 | `lme_harness.v2.py` |
| C3 `aimem-qwen3`, rows 1–31 | v3-pre (`15b4fe3e…`), straight to the embed server on port 11436, no cache | `reconstructed/lme_harness.v3pre.py` |
| C3, rows 32–348 | v3 (`b59ee6f5…`) through `run_queue.sh` and the cache proxy on port 11439, macOS 26.5 | `lme_harness.py`, `mac-drivers/run_queue.sh`, `embed_cache_proxy.py` |
| C3, rows 349–470 | v3 through `run_c3_resume.sh` and the proxy, macOS 27.0 (the A15.2 deviation) | `lme_harness.py`, `mac-drivers/run_c3_resume.sh`, `embed_cache_proxy.py` |
| C3 checks kept out of the analysis (A13, A15.2): the cache warm-up (31 questions) and the macOS 27.0 drift check (20) | v3; the warm-up through the proxy, the drift check straight to port 11436 | `lme_harness.py`, `mac-drivers/run_c3_resume.sh` |
| D3 `am-qwen3` (12 of 470 rows, excluded by A15.2) and the slot smoke test | v3-pre through `run_d3.sh` | `reconstructed/lme_harness.v3pre.py`, `mac-drivers/run_d3.sh` |
| C4, C5, C6 | never ran on the Mac | none |
| `report-interim` (md `911f6f1d…`) and `report-mac-descriptive` (md `62c00791…`) | summarizer v3 importing harness v3 | `lme_summarize.py`, `lme_harness.py` |

- **v1a.** `lme_harness.v1.py` is v1a plus six lines: the A8 arms-table entries for
  `aimem-qwen3-8b` and `aimem-qwen3-0.6b`, added at 19:10, after B1, B2 and D1 had loaded v1a.
  For those three arms the two files behave the same. Two methods rebuild the same v1a bytes:
  replaying the session's recorded write and its five edits up to 18:54, and deleting those six
  lines from `lme_harness.v1.py`. B2 and D1 were paused from 19:20 to 20:32 and kept the code they
  had loaded. An 8-row C2 attempt that loaded the bytes now in `lme_harness.v1.py` was stopped
  at 19:19 and discarded; C2 then ran from row 0 on v2.
- **v3-pre.** It adds A11 to v2. v3 adds A12 to it: the reranker endpoint, the fallback counters
  and the C4 worker count, none of which the `aimem-qwen3` arm uses. The file comes from the
  session's file-history snapshot of 21:42 and matches a replay of the 21:37 edit onto v2. C3
  therefore mixes two harness revisions and two macOS versions; A15.2 records the second.
- **The reports.** On 2026-09-25, `lme_summarize.py` and `lme_harness.py` from this directory,
  run with a fresh checkout of the official code at `9e0b455` and a Python 3.11.16 venv built from
  the pins below, reproduced `report-mac-descriptive.md` (`62c0079136d5…`) and `.json`
  (`dbd8315da1d9…`) byte for byte from the recorded Mac rows. They also reproduced
  `report-interim.md` (`911f6f1df0a6…`) and `.json` (`b9ed7a799cfb…`) with C3 cut to the 139
  rows it had at 23:35. This replays the preregistered analysis on recorded rows; no arm ran.

The agent-ecosystem LongMemEval lane branch (its PR #49, open) committed the same v3 sources in
`ef002f51`. At its head, `576689af`, the harness and summarizer are the v4 that A15.2 names and
the proxy has changed too, while `reference/lme_harness_v3.py`, `eligible-manifest.json`,
`run_official_oracle.py` and the agentmemory pair still match the files here byte for byte.

## Pins fetched at run time

| Input | Pin |
| --- | --- |
| Official code | `xiaowu0162/LongMemEval` at `9e0b455f4ef0e2ab8f2e582289761153549043fc` (MIT; `LICENSE` sha256 `d3c4b9aa54759df6ded337978a6f3b55b75615e5e4525c3b82d7e2627d4b9732`). The harness imports `evaluate_retrieval` and `process_item_flat_index` from it at run time; nothing is copied. |
| Dataset | `longmemeval_s_cleaned.json` from the Hugging Face dataset `xiaowu0162/longmemeval-cleaned` at revision `98d7416c24c778c2fee6e6f3006e7a073259d48f`: sha256 `d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442`, 277,383,467 bytes. Fetch `resolve/98d7416c24c778c2fee6e6f3006e7a073259d48f/longmemeval_s_cleaned.json` and check the sha256 (the upstream README fetches `resolve/main`). The harness reads it from `data/` next to itself. |
| ai-memory (C1–C3) | a local `cargo build --locked` of `19b6429` (`release/2.5`), binary sha256 `f553b4025272943fa725ed6f297d94a6c416d3172b96ec765575792a5187fd51` (arm64 macOS). #274 states that the user chose the official v2.4.0 release as the control for the workstation rerun. This repository has no other record of that choice, so A17 has to state it. |
| agentmemory (D1–D3) | the lock in `agentmemory/`, and the iii engine from release `iii/v0.11.2` of `iii-hq/iii` (published 2026-04-21). Asset digests: `iii-aarch64-apple-darwin.tar.gz` `e7834c44fefb2b5343d327102a941419245f7fff447f95373857a04b033fb1bd` (the Mac's copy), `iii-x86_64-unknown-linux-gnu.tar.gz` `9c83c47788b4ef4beeb65dd9bf37e94f993770cd3db874464c3ce1cdc92352cd`. The lock does not cover the engine binary. |
| MiniLM for C2 | `sentence-transformers/all-MiniLM-L6-v2`, fetched without a pinned revision; the Mac's `model.safetensors` has sha256 `53aa51172d142c89d9012cce15ae4d6cc0ca6895895114379cacb4fab128d9db`. The harness copies it from `models/all-MiniLM-L6-v2` next to itself. |
| MiniLM for D2 | `Xenova/all-MiniLM-L6-v2` (q8), which transformers.js 4.3.0 fetches on first use into its package cache; the Mac's `onnx/model_quantized.onnx` has sha256 `afdb6f1a0e45b715d0bb9b11772f032c399babd23bfc31fed1c170afc848bdb1` (22,972,370 bytes). The lock does not pin it. |
| Embedding and LLM servers | Ollama 0.34.4 with the `qwen3-embedding` digests and settings in A11 and A15. `LME_EMBED_URL` and `LME_LLM_URL` replace the default `http://127.0.0.1:11434`. |
| Node | v24.21.0 from mise when checked on 2026-09-25; the version at run time was not recorded. The harness resolves `mise which node` when an arm starts. |
| Python | CPython 3.11.16 (the preregistration's stated deviation from upstream's 3.9) with the packages below. No lockfile was written when the venv was built; this is `uv pip freeze` of the Mac venv on 2026-09-25, after the runs. |

```text
annotated-types==0.8.0
anyio==4.15.1
backoff==2.2.1
certifi==2026.7.22
charset-normalizer==3.5.1
click==8.5.0
cloudpickle==3.1.2
distro==1.9.0
filelock==4.0.3
fsspec==2026.9.0
h11==0.16.0
httpcore==1.0.9
httpx==0.27.2
huggingface-hub==0.23.4
idna==3.20
jinja2==3.1.6
joblib==1.6.0
markupsafe==3.0.3
mpmath==1.3.0
networkx==3.6.1
nltk==3.9.1
numpy==1.26.3
openai==1.35.1
packaging==26.3
pillow==12.3.0
pydantic==2.13.5
pydantic-core==2.46.5
pyyaml==6.0.3
rank-bm25==0.2.2
regex==2026.9.10
requests==2.34.2
safetensors==0.8.0
scikit-learn==1.5.1
scipy==1.16.3
sentence-transformers==2.2.2
sentencepiece==0.2.0
sniffio==1.3.1
sympy==1.14.0
threadpoolctl==3.7.0
tokenizers==0.19.1
torch==2.3.1
torchvision==0.18.1
tqdm==4.66.4
transformers==4.43.3
typing-extensions==4.16.0
typing-inspection==0.4.4
urllib3==2.8.0
```

## Paths the copied code expects

The harness and summarizer contain no Mac-only path; the scripts in `mac-drivers/` do.

- Every harness revision imports numpy and then the official code from
  `$HOME/.local/share/agent-ecosystem/src/LongMemEval` at module load, before it parses
  arguments. The official `run_retrieval.py` in turn imports torch, tqdm, rank-bm25,
  sentence-transformers, openai, transformers and scikit-learn. So `--help` needs that checkout
  and those packages.
- When an arm runs, the harness starts ai-memory from
  `$HOME/.local/share/agent-ecosystem/tools/ai-memory-2.5.0-19b6429/ai-memory` and agentmemory
  from `$HOME/.local/share/agent-ecosystem/bench/agentmemory` (`bin/iii` and `node_modules/`), and
  finds node through `mise` (falling back to `$HOME/.local/bin/mise`). agentmemory stores go
  under `/tmp`, and every server binds to 127.0.0.1. These paths are relative to `$HOME`, so a
  home directory that maps them is enough on Linux as on macOS. The harness also needs the Unix
  `fcntl` module and the `pgrep` and `lsof` commands.
- The harness reads `data/longmemeval_s_cleaned.json`, `eligible-manifest.json` and `models/`
  next to itself and writes `results/<arm>.jsonl` there unless `--out` is given. The summarizer
  reads `results/`, `results-cachewarm/` and `official-logs/` next to itself. To run a file from
  `reconstructed/`, copy it next to `eligible-manifest.json` first.
- `mac-drivers/` records how the Mac launched C3 and D3; the scripts are not portable. They call
  `/Applications/LM Studio.app/...`, select Apple Metal runtimes, start Ollama from the Mac's
  layout, wait on Mac process ids and run the Mac venv. They were syntax-checked with `zsh -n`
  only. `run_d3.sh` fails that check at line 13 (`redirection with no command`), a false positive
  for `$PY - <<EOF` that a four-line script reproduces while running it succeeds; the script ran
  on 2026-09-24.

## Checking `--help` from a clean clone

Run from a clean clone, on the coordinator Mac, on 2026-09-25, with `env -i` and the home
directory named below:

| Python | Home directory | Result |
| --- | --- | --- |
| the system Python 3.9.6, or uv CPython 3.14.7 | empty | every harness revision and `lme_summarize.py`: exit 1, `ModuleNotFoundError: No module named 'numpy'`; `run_official_oracle.py`: exit 1, `No module named 'torch'` |
| a 3.11.16 venv with the pins above | empty | every harness revision and `lme_summarize.py`: exit 1, `ModuleNotFoundError: No module named 'src'` (the official code is missing) |
| the same venv | holds only a fresh `git clone` of the official code at `9e0b455`, at the path above | each harness revision: exit 0 with its usage, for v3 `usage: lme_harness.py [-h] [--limit LIMIT] [--ids [IDS ...]] [--workers WORKERS] [--out OUT] arm`; `lme_summarize.py`: exit 0, `usage: lme_summarize.py [-h] [--incumbent INCUMBENT] [--out OUT] [--final]`; `run_official_oracle.py`, started in the official `src/retrieval` with the official root on `PYTHONPATH`: exit 0, the official runner's usage |

`embed_cache_proxy.py` has no `--help`: it takes `UPSTREAM PORT DB [--selftest MODEL]`, and
`--help` alone exits 1 with `IndexError`. With the system Python 3.9.6, an empty home directory
and a synthetic upstream that returns a fixed vector, `--selftest` exits 0 and prints
`proxied hit byte-identical=True; recomputation identical=True`.

The steps behind the passing row, for another host (checked here on macOS arm64 only):

```sh
LME_HOME="$(mktemp -d)"   # a home directory holding only the official code
git clone https://github.com/xiaowu0162/LongMemEval "$LME_HOME/.local/share/agent-ecosystem/src/LongMemEval"
git -C "$LME_HOME/.local/share/agent-ecosystem/src/LongMemEval" checkout 9e0b455f4ef0e2ab8f2e582289761153549043fc
uv venv --python 3.11 lme-venv && uv pip install --python lme-venv/bin/python -r pins.txt   # pins.txt: the list above
HOME="$LME_HOME" lme-venv/bin/python lme_harness.py --help
```

## Restoring the agentmemory install

The lock and `package.json` are stored as `agentmemory/package-lock.json.frozen` and
`agentmemory/package.json.frozen`. Put them back under their npm names in the prefix the harness
expects, then install:

```sh
AM_ROOT="$HOME/.local/share/agent-ecosystem/bench/agentmemory"
mkdir -p "$AM_ROOT"
cp agentmemory/package.json.frozen "$AM_ROOT/package.json"
cp agentmemory/package-lock.json.frozen "$AM_ROOT/package-lock.json"
(cd "$AM_ROOT" && npm ci --ignore-scripts)
```

- Keep optional dependencies. `--omit=optional` drops transformers.js and onnxruntime-node, and
  D2's local embeddings with them. `--ignore-scripts` skips only the onnxruntime-node and
  protobufjs install scripts. The onnxruntime-node script only downloads CUDA providers; its CPU
  binaries ship in the package.
- `npm ci --dry-run --ignore-scripts` on the restored pair (npm 11.19.0, node v24.21.0, an empty
  npm configuration and cache) exits 0 with "added 186 packages", the same name@version set as
  the Mac's installed tree.
- Download the iii release asset for the host, check its digest from the table above, and put
  the `iii` binary at `$AM_ROOT/bin/iii`.
- **Why the files are renamed.** osv-scanner 2.6.0 (`--no-resolve`, this repository's
  configuration) finds two advisories in the lock, both reached through `iii-sdk` 0.11.2:
  GHSA-45rx-2jwx-cxfr (high, CVSS 7.5, `@opentelemetry/propagator-jaeger` 1.30.1, fixed in 2.9.0)
  and GHSA-8988-4f7v-96qf (medium, CVSS 5.3, `@opentelemetry/core` 1.30.1, fixed in 2.8.0). Under
  their npm names the files would fail the required `dependency-review` check and, once the
  coverage test puts them in the scan inventory, the required `osv-scanner` check. Upgrading
  them would change the measured system, so the lock is kept as a record under names no scanner
  reads. The decision, its alternatives and what would overturn it are in
  [docs/decisions/2026-09-25-longmemeval-frozen-npm-lock.md](../../../docs/decisions/2026-09-25-longmemeval-frozen-npm-lock.md).
  Restore the files only into an isolated prefix for a benchmark run.

## Not committed, and why

- **The dataset and the official oracle file** (`data/`): fetched by sha256 at run time, as #274
  asks; see [Licences](#licences).
- **Run outputs:** result rows (`results*/`, 470 rows per complete arm), the official runner's
  logs (about 291 MB each, holding dataset text), run logs (`logs/`; one holds an absolute home
  path), embedding caches (`cache/`, about 660 MB), model weights (`models/`) and the Python venv.
  #274 does not ask for them.
- **The two reports** and their JSON: not requested. `convergence.json` carries their figures, and
  the summarizer here reproduces both byte for byte (above).
- **The two Codex reviews** the preregistration cites, `prereg-review-codex.md` (A1–A7) and
  `harness-review-codex.md` (A10), and their event-stream logs: they fail this repository's
  private-content scan (a home path; the logs also hold session identifiers), so they cannot be
  committed byte-exact.
- **`lme_summarize.v1.py`** (`e01b78bc885e9458d0b95f5d851c45d1b63d2b897eec8b15884c1ed1b594a91f`)
  **and `lme_summarize.v2.py`** (`29f2f0b7fa5e7c426c8b14f37ebd910c9b19e9a82aa8a15e18de5feef9caa200`),
  the copies A13 and A14 keep: neither produced a recorded report.
- **`run_tail.sh`** (`9e30e42ec09832d336d8a9d5b1a736fbfe466c9675e9602659a76f609980423f`): it was
  superseded at 22:38 while still waiting and never ran an arm.
- **The inline launch commands:** the A0 and A1 official runs, the arm chains started at 18:55,
  18:57, 20:32 and 21:37, the embed server started at 21:35 and the proxy started at 22:38. They
  exist only in the coordinator session's transcript, with home paths; the arm table above gives
  each one's time and arms.
- **Later preregistration revisions:** the Mac's current file adds A16.1–A16.3 (sha256
  `a9b1db335eee1ff99d1883e048bcd8e443ca2afee3505a34fd874dd1ef412d5b`, 37,885 bytes), and its first
  33,527 bytes are `PREREGISTRATION.md` here. #274 asks for the A1–A16 revision.
- **Binaries:** the ai-memory build, the iii engine and `node_modules/`, pinned above.

## Licences

- LongMemEval code: MIT, Copyright (c) 2024 Di Wu, at `9e0b455`. It is imported at run time, not
  copied.
- The dataset: MIT on its Hugging Face card, not gated. It is not committed: #274 asks for a fetch
  at run time, the file is 277 MB, and its filler sessions come from ShareGPT and UltraChat
  (upstream README).
- `eligible-manifest.json` holds the dataset sha256 and question ids only, no question or session
  text.
- The preregistration, harness, summarizer and scripts are the owner's own work, kept until now on
  the Mac and in the private agent-ecosystem repository. Committing them publishes them under this
  repository's root MIT licence ([licenses/README.md](../../../licenses/README.md)).
- The lock and `package.json` are npm metadata (names, versions, URLs and integrity values); no
  package code is committed. `@agentmemory/agentmemory` is Apache-2.0.

## Verifying

```sh
cd blueprints/memory-stack/longmemeval
sha256sum --check --strict SHA256SUMS   # on macOS also: shasum -a 256 -c SHA256SUMS
```

`SHA256SUMS` lists every file here except itself, relative to this directory. The same files are
registered in `manifests/evidence.json`, and `python3 scripts/validate.py` checks their sha256 and
size.

| Claim | Evidence class | How |
| --- | --- | --- |
| The files match the Mac originals and commit `2c3e09b` | `source_review` | sha256 of every source against `SHA256SUMS`. A checksum proves byte identity, not that the bytes describe an adequate test. |
| Which code produced which arm | `source_review` | logs, row schemas, file times, bytecode headers and the session's edit history, read only |
| The summarizer and harness v3 reproduce both reports from the recorded rows | `local_integration` | the replay above, on the Mac, outputs in a scratch directory |
| `--help` from a clean clone | `local_integration` | the table above |
| The proxy's self-test | `synthetic` | a stub upstream that returns a fixed vector |
| Any benchmark result | none new | no arm ran for this commit |
