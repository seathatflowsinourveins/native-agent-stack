# Next stages on the new hosts

Dated 2026-09-23. This page says which machine does what, what to run on each, and which upgrades the
measured load justifies. The per-layer list of what to install is generated in
[`new-host-grand-list.md`](new-host-grand-list.md); the step-by-step install is
[`adoption/bootstrap.md`](../adoption/bootstrap.md); recording what ran is
[`contributing-evidence.md`](contributing-evidence.md). For the exact ordered commands
(measure, record, refresh the derived views, check for a possible verdict flip, validate),
see [`contributing-evidence.md`'s "The new-host loop, in one place"](contributing-evidence.md#0-the-new-host-loop-in-one-place);
moving a set-up host to a later release is
[moving a host to a new release](../adoption/update.md#moving-a-host-to-a-new-release).

## Machine roles (recommendation, not a measurement)

| Host | Role | Why |
| --- | --- | --- |
| 128 GB WSL workstation (RTX 4090, 24 GB) | Primary always-on host for the shared local services (embedder, Qdrant, ai-memory, observability) and the north-star engine and paper lanes | Same CUDA/vLLM software stack as the measured host, but a different GPU generation: requalify each model there before pinning (as [`new-workstation-runtime-profile-20260922.md`](new-workstation-runtime-profile-20260922.md) says); projected tiers `large-32b-q4` generation, `headroom` semantic RAG, concurrency cap 16 |
| RTX 5090 Laptop, 48 GB WSL (measured host) | Development host; stays the reference for measured evidence | `native_proven` profile; the tiers above were measured here |
| macOS arm64, 64 GB | Portable host and the macOS acceptance lane (MLX / llama.cpp Metal) | Projected `large-32b-q4` from about 38 GB of shared memory; no macOS workstation run exists, so acceptance is the open item |

The workstation and macOS tiers are labelled projections in
[`adoption/hardware-profiles.json`](../adoption/hardware-profiles.json) until
`python3 scripts/hardware_profile.py --record-host <host-id>` runs on each host. It adds a
dated, `native_proven` measured entry next to the projection -- it does not remove or
overwrite the projection entry itself -- so once a host has a measured entry, prefer that one
and treat the projection as superseded guidance rather than looking for it to have vanished.

## Workstation (WSL2) next steps

1. Windows side: set `%UserProfile%\.wslconfig` to the decided workstation profile, then
   `wsl --shutdown` once:

   ```ini
   [wsl2]
   memory=112GB
   processors=60
   swap=16GB
   networkingMode=mirrored
   [experimental]
   autoMemoryReclaim=gradual
   sparseVhd=true
   ```

   Decided 2026-09-23 (user decision, evidence in the upgrade manifest below): the workstation's main
   work is the native LLM ecosystem, the foundation and the north star, so WSL gets about 88% of the
   128 GB and Windows keeps 16 GB. On the measured laptop (63.4 GB physical, WSL capped at 48 GB)
   Windows outside WSL held about 24 GB with 9 GB free, and commit charge was 85.7 of 99.7 GB, so a
   cap near the full 128 GB would leave Windows paging under load. `autoMemoryReclaim=gradual` returns
   idle Linux cache to Windows. After setup, re-measure under full load; raise toward 116-120 GB only
   if Windows keeps more than 12 GB free. This replaces the 96 GB proposal in the
   [workstation runtime profile](new-workstation-runtime-profile-20260922.md), which under the
   profiles' own arithmetic would just miss the `headroom` tier.
2. Pinned clone at the release tag, then `adoption/bootstrap-linux.sh` (bootstrap step 0 onward).
3. `python3 scripts/hardware_profile.py --record-host <host-id>` (`<host-id>` like
   `wsl-workstation-20261015`); this writes the measured report and adds the entry to the
   hardware profiles for you, replacing the earlier by-hand edit.
4. Profiles in order: `foundation-cpu`, `research-runtime`, `observability`, `semantic-rag`,
   `recovery`, `trading-nautilus` (see the grand list's setup order).
5. Record each component that ran with `python3 scripts/host_receipts.py record`
   (`--qualified-model` for any local runtime model you qualified there), then
   `python3 scripts/component_matrix.py --write` and `python3 scripts/new_host_grand_list.py --write`.
6. North star on this host: the engine replay, then IBKR local acceptance and the adaptive paper
   broker trial as the gate ladder
   ([`catalogs/us-equities/gates-20260922.json`](../catalogs/us-equities/gates-20260922.json)) allows.
   Paper only; nothing here authorizes live orders.

## macOS (64 GB) next steps

1. Pinned clone, then `adoption/bootstrap-macos.sh`. The Homebrew prerequisite install, the
   `socraticode`, darwin-binary and embedding-model pins, the launchd agents and the embedding
   acceptance script all came in #94, after `v2026.09.23`: at that tag the script brews only `jq`
   and installs 7 of the 8 `macos-arm64-foundation` components, and the launchd and embedding steps
   run from a default-branch clone, as the [macOS page](../adoption/platforms/macos-arm64.md) marks.
   A release cut after #94 and re-pinned ([moving a host to a new release](../adoption/update.md#moving-a-host-to-a-new-release))
   removes these differences.
2. `python3 scripts/hardware_profile.py --record-host <host-id>` and the MLX smoke; this writes
   and registers the measured profile.
3. `macos-arm64-foundation` profile; re-qualify any local model on MLX or llama.cpp Metal: a vLLM
   result on CUDA does not transfer. Record a qualified model with
   `python3 scripts/host_receipts.py record ... --qualified-model '{"runtime": "mlx-lm", ...}'`.
4. Record receipts as above. The first real macOS run is what moves the `macos-arm64` column of the
   grand list off `untested`.

## Upgrades: only what the measurement supports

The manifest is
[`evidence/artifacts/host-upgrade-20260923/upgrade-evidence.json`](../evidence/artifacts/host-upgrade-20260923/upgrade-evidence.json).

| Item | Verdict | Evidence in one line |
| --- | --- | --- |
| Workstation WSL memory: 112 GB (decided) | Needed at setup | `headroom` tier needs about 96 GB visible; Windows keeps 16 GB (measured Windows-side use about 24 GB on the laptop) |
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
