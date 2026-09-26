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
| macOS arm64: Apple M5 Pro, 24 GB in service (measured); a 64 GB replacement is recommended | Cockpit and coordinator: native Claude and Codex clients, review and integration, light local work, second-machine paper trials and the macOS acceptance lane (MLX / llama.cpp Metal) | Measured on 2026-09-24: the 24 GB host is RAM-limited for its current load and cannot hold the 27B local model ([evidence](../evidence/artifacts/host-upgrade-20260924/upgrade-evidence.json)); heavy agent sessions and the always-on lanes stay on the workstation |

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

   Note added 2026-09-25: `sparseVhd=true` has no effect on current WSL. WSL 2.7.14 creates every
   new VHD non-sparse "while data corruption is being debugged" and prints "Sparse VHD support is
   currently disabled due to potential data corruption"
   ([`WslCoreFilesystem.cpp`](https://github.com/microsoft/WSL/blob/2.7.14/src/windows/common/WslCoreFilesystem.cpp#L35-L39)).
   Making an existing distribution sparse needs
   `wsl --manage <distro> --set-sparse true --allow-unsafe`
   ([microsoft/WSL#13075](https://github.com/microsoft/WSL/issues/13075)); this page does not
   recommend it. To reclaim VHD space instead, run `sudo fstrim -v /` in the distribution, then
   `wsl --shutdown` and compact its `ext4.vhdx`
   ([location](https://learn.microsoft.com/en-us/windows/wsl/disk-space#how-to-locate-the-vhdx-file-and-disk-path-for-your-linux-distribution))
   offline from an elevated prompt: `diskpart` with `select vdisk file="<path>"`,
   `attach vdisk readonly`, `compact vdisk` and `detach vdisk`, or, with the Hyper-V module,
   `Mount-VHD -Path <path> -ReadOnly`, `Optimize-VHD -Path <path> -Mode Full` and
   `Dismount-VHD -Path <path>`. `-Mode Full` on a VHDX that is not attached read-only falls back to
   `Prezeroed` mode. Both tools compact only a detached or read-only disk. WSL's
   own disk-space page uses `diskpart` only to expand a VHD and warns that Windows tools on WSL's
   `AppData` files can corrupt a distribution, so export or back up the distribution first.

   The workstation's live `%UserProfile%\.wslconfig`, read on 2026-09-25, differs from the
   projection above: `memory=104GB`, `processors=48`, `swap=24GB`, `networkingMode=mirrored` and
   `[experimental] autoMemoryReclaim=dropCache`, with no `sparseVhd` (that file records removing it
   on 2026-09-08 as inert), plus host-specific swap-file, crash-dump and idle-timeout keys. Inside
   WSL, `nproc` returned 48 and `free -g` 102 GiB of memory and 24 GiB of swap. The projection and
   its 2026-09-23 decision are left as recorded.
2. Pinned clone at the release tag, then `adoption/bootstrap-linux.sh` (bootstrap step 0 onward).
3. `python3 scripts/hardware_profile.py --record-host <host-id>` (`<host-id>` like
   `wsl-workstation-20261015`); this writes the measured report and adds the entry to the
   hardware profiles for you, replacing the earlier by-hand edit.
4. Profiles in order: `foundation-cpu`, `research-runtime`, `observability`, `semantic-rag`,
   `recovery`, `trading-nautilus` (see the grand list's setup order). `token-efficiency` is fully
   pinned on this platform too (`adoption/README.md`'s profile table); follow
   [`docs/token-session-handbook.md`](token-session-handbook.md#new-pc-either-platform-the-complete-token-efficiency-practice)
   for its bootstrap, Codex user-scope MCP servers and coverage-check order.
5. Record each component that ran with `python3 scripts/host_receipts.py record`
   (`--qualified-model` for any local runtime model you qualified there), then
   `python3 scripts/component_matrix.py --write` and `python3 scripts/new_host_grand_list.py --write`.
   A `--stage use` receipt of a component that several catalog layers list names the layer(s) it
   exercised with `--layer-ref <catalog>/<layer_id>`
   ([contributing evidence](contributing-evidence.md), section 3 step 3; changed after `v2026.09.26`).
6. North star on this host: the engine replay, then IBKR local acceptance and the adaptive paper
   broker trial as the gate ladder
   ([`catalogs/us-equities/gates-20260922.json`](../catalogs/us-equities/gates-20260922.json)) allows.
   Paper only; nothing here authorizes live orders.

## macOS next steps (replacement Mac)

The 24 GB Mac is being replaced (see the upgrade table below). On the replacement:

0. Sign in natively to Claude, Codex and `gh`; never copy another host's credential stores or memory
   database. The shared foundation services (ai-memory, Ollama, Qdrant, the user-scope MCP servers,
   the QMD and SocratiCode indexes, mise tools) come from agent-ecosystem through its single writer
   ([agent-ecosystem#28](https://github.com/seathatflowsinourveins/agent-ecosystem/issues/28)). Where
   those services exist, skip the launchd agents of `adoption/bootstrap-macos.sh` in step 1: they
   would start a second Qdrant and a second ai-memory store.
1. Pinned clone, then `adoption/bootstrap-macos.sh`. The pinned release contains #94 (the Homebrew
   prerequisite install, the `socraticode`, darwin-binary and embedding-model pins, the launchd
   agents and the embedding acceptance script), so every step on the
   [macOS page](../adoption/platforms/macos-arm64.md) runs from the pinned checkout.
   `token-efficiency` is a separate profile, fully pinned on this platform on main
   (`adoption/README.md`'s profile table); its last eight macOS pins came after the pinned
   `v2026.09.26`, so at that tag pass them in `--allow-unpinned` and use their recipes. Follow
   [`docs/token-session-handbook.md`](token-session-handbook.md#new-pc-either-platform-the-complete-token-efficiency-practice)
   for its own bootstrap, Codex user-scope MCP servers and coverage check.
2. `python3 scripts/hardware_profile.py --record-host <host-id>` and the MLX smoke; this writes
   and registers the measured profile.
3. `macos-arm64-foundation` profile; re-qualify any local model on MLX or llama.cpp Metal: a vLLM
   result on CUDA does not transfer. Record a qualified model with
   `python3 scripts/host_receipts.py record ... --qualified-model '{"runtime": "mlx-lm", ...}'`,
   adding `--layer-ref` at `--stage use` when several layers list the runtime (changed after `v2026.09.26`).
4. Record receipts as above, with `--layer-ref` where several layers list the component
   (changed after `v2026.09.26`). The first real macOS run is what moves the `macos-arm64` column of
   the grand list off `untested`.
5. Run the RAM-fit matrix and the embedder and reranker comparisons listed as open items in
   [`foundation-alignment.json`](../evidence/artifacts/host-upgrade-20260924/foundation-alignment.json),
   as scratch processes, and hand the numbers to the foundation-lane owner.
6. Send heavy sessions to the workstation: run `sshd` inside WSL, add the workstation as an SSH
   connection in Claude desktop (an SSH session reads MCP servers, hooks, settings and skills from the
   remote's own `~/.claude`), and check the Claude Code version Desktop installs there against the
   pinned floor. For runs that must outlive the laptop session, start Claude Code in `tmux` on the
   workstation and use Remote Control.

## Upgrades: only what the measurement supports

The manifest is
[`evidence/artifacts/host-upgrade-20260923/upgrade-evidence.json`](../evidence/artifacts/host-upgrade-20260923/upgrade-evidence.json).
The macOS host's measured follow-up, which supersedes that manifest's projected-64 GB MacBook item,
is [`evidence/artifacts/host-upgrade-20260924/upgrade-evidence.json`](../evidence/artifacts/host-upgrade-20260924/upgrade-evidence.json).

| Item | Verdict | Evidence in one line |
| --- | --- | --- |
| Workstation WSL memory: 112 GB (decided) | Needed at setup | `headroom` tier needs about 96 GB visible; Windows keeps 16 GB (measured Windows-side use about 24 GB on the laptop) |
| CPU limit in `ecosystem-bounded-run` | Needed now (software) | Unlimited Gitleaks scans were 72% of measured CPU, up to 8.4 cores |
| Retention for per-wave state and caches | Needed now (software) | About 65 GiB of wave caches and state with no retention rule |
| GPU memory above 24 GB | Not needed now | Median GPU use 6.5%; embedder plus 8B worker peaked at 20,217 of 24,463 MiB |
| 256 GB RAM on the workstation | Not needed now | No selected model needs RAM offload; candidates are unverified here |
| Laptop RAM, disk | Not needed | 24-26 GiB RAM free under full load; 827 GB disk free |
| MacBook memory: 24 GB in service | Needed (measured 2026-09-24) | 26.84 GiB of process footprint on 24 GiB, 357.8 GiB of swap writes in 4.8 days; the RAG embedder leaves 2.1 GiB free; the 27B model exceeds the 17.76 GiB Metal limit. Recommended: 64 GB (M5 Pro) |

Status on 2026-09-24:
- **CPU limit.** It is implemented in
  [`adoption/tools/ecosystem-bounded-run`](../adoption/tools/README.md#cpu-quota-2026-09-24): a per-job
  `CPUQuota` of (CPUs − 2) × 100%, checked inside the scope, on hosts whose user manager delegates cpu
  (systemd 252 and later). The default leaves two CPUs free, so it does not throttle the measured 8.4-core
  scan. The interactive-contention part stays open until the comparison named on that page has run.
- **Retention.** The authoring host has a report-only retention rule for its wave state and caches. It
  deletes nothing, and on 2026-09-24 it found no eligible candidate, because committed evidence cites wave
  paths. Archiving when a wave's record closes still needs a wave-closure marker and the export of cited
  raw files.
- **macOS memory.** The 24 GB Mac is RAM-limited by measurement, and the user decided to switch once
  that was shown. The recommended replacement is a 64 GB M5 Pro used as the cockpit and coordinator
  ([upgrade evidence](../evidence/artifacts/host-upgrade-20260924/upgrade-evidence.json)). The two
  memory-kill events on 2026-09-24 came from an unbounded gitleaks scan, which #193 bounds separately.
  Memory, RAG and foundation alignment on the Mac, with the model candidates and open items, is in
  [`foundation-alignment.json`](../evidence/artifacts/host-upgrade-20260924/foundation-alignment.json).

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
