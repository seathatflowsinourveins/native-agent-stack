# Next stages on the new hosts

Dated 2026-09-23. This page says which machine does what, what to run on each, and which upgrades the
measured load justifies. The per-layer list of what to install is generated in
[`new-host-grand-list.md`](new-host-grand-list.md); the step-by-step install is
[`adoption/bootstrap.md`](../adoption/bootstrap.md); recording what ran is
[`contributing-evidence.md`](contributing-evidence.md).

## Machine roles (recommendation, not a measurement)

| Host | Role | Why |
| --- | --- | --- |
| 128 GB WSL workstation (RTX 4090, 24 GB) | Primary always-on host for the shared local services (embedder, Qdrant, ai-memory, observability) and the north-star engine and paper lanes | Same CUDA/vLLM software stack as the measured host, but a different GPU generation: requalify each model there before pinning (as [`new-workstation-runtime-profile-20260922.md`](new-workstation-runtime-profile-20260922.md) says); projected tiers `large-32b-q4` generation, `headroom` semantic RAG, concurrency cap 16 |
| RTX 5090 Laptop, 48 GB WSL (measured host) | Development host; stays the reference for measured evidence | `native_proven` profile; the tiers above were measured here |
| macOS arm64, 64 GB | Portable host and the macOS acceptance lane (MLX / llama.cpp Metal) | Projected `large-32b-q4` from about 38 GB of shared memory; no macOS workstation run exists, so acceptance is the open item |

The workstation and macOS tiers are labelled projections in
[`adoption/hardware-profiles.json`](../adoption/hardware-profiles.json) until
`python3 scripts/hardware_profile.py` runs on each host and replaces them.

## Workstation (WSL2) next steps

1. Windows side: raise `.wslconfig` memory from WSL's default of half the physical RAM, using the
   [workstation runtime profile](new-workstation-runtime-profile-20260922.md) (it proposes
   `memory=96GB processors=60 swap=16GB`; the hardware profiles assume 100 GB for the `headroom` tier,
   which 96 GB would just miss; the owners reconcile the value), then `wsl --shutdown` once.
2. Pinned clone at the release tag, then `adoption/bootstrap-linux.sh` (bootstrap step 0 onward).
3. `python3 scripts/hardware_profile.py`; add the measured entry to the hardware profiles.
4. Profiles in order: `foundation-cpu`, `research-runtime`, `observability`, `semantic-rag`,
   `recovery`, `trading-nautilus` (see the grand list's setup order).
5. Record each component that ran with `python3 scripts/host_receipts.py record`, then
   `python3 scripts/component_matrix.py --write` and `python3 scripts/new_host_grand_list.py --write`.
6. North star on this host: the engine replay, then IBKR local acceptance and the adaptive paper
   broker trial as the gate ladder
   ([`catalogs/us-equities/gates-20260922.json`](../catalogs/us-equities/gates-20260922.json)) allows.
   Paper only; nothing here authorizes live orders.

## macOS (64 GB) next steps

1. Pinned clone, then `adoption/bootstrap-macos.sh` (the macOS clean-install work in progress adds
   Homebrew prerequisites, launchd agents and darwin pins).
2. `python3 scripts/hardware_profile.py` and the MLX smoke; record the measured profile.
3. `macos-arm64-foundation` profile; re-qualify any local model on MLX or llama.cpp Metal: a vLLM
   result on CUDA does not transfer.
4. Record receipts as above. The first real macOS run is what moves the `macos-arm64` column of the
   grand list off `untested`.

## Upgrades: only what the measurement supports

The manifest is
[`evidence/artifacts/host-upgrade-20260923/upgrade-evidence.json`](../evidence/artifacts/host-upgrade-20260923/upgrade-evidence.json).

| Item | Verdict | Evidence in one line |
| --- | --- | --- |
| Workstation WSL memory above the 64 GB default | Needed at setup | The `headroom` tier needs about 96 GB visible |
| CPU limit in `ecosystem-bounded-run` | Needed now (software) | Unlimited Gitleaks scans were 72% of measured CPU, up to 8.4 cores |
| Retention for per-wave state and caches | Needed now (software) | About 65 GiB of wave caches and state with no retention rule |
| GPU memory above 24 GB | Not needed now | Median GPU use 6.5%; embedder plus 8B worker peaked at 20,217 of 24,463 MiB |
| 256 GB RAM on the workstation | Not needed now | No selected model needs RAM offload; candidates are unverified here |
| Laptop RAM, disk, MacBook | Not needed | 24-26 GiB RAM free under full load; 827 GB disk free |

If a selected local model later outgrows 24 GB, buy GPU memory first (a 48 or 96 GB workstation card
or a second GPU); system RAM only helps mixture-of-experts models served partly from RAM.
Trillion-parameter checkpoints are hosted-API models for every listed host (for example
[MiMo-V2.6-Pro-RL](https://huggingface.co/XiaomiMiMo/MiMo-V2.6-Pro-RL): 1.02 trillion parameters by
the Hugging Face API, about 1 TB stored).

## Local model slots

Code embeddings use Nemotron-3-Embed-1B (July 2026). The memory embedder is still
all-MiniLM-L6-v2 (2022), a known gap; replacing it needs a matched retrieval comparison and the
lane re-record. The key-free local worker Qwen3-8B-AWQ qualified once on 2026-09-23 (20/20 tool
calls, 4/5 tasks) and is not served; serving it on demand is a recommendation, not a setup step.
Layer verdicts change only through the lane re-record, not through this page.
