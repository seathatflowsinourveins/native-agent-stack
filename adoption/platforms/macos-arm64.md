# **Drafted, not accepted — nothing on this page was executed on a Mac**

Per [the acceptance evidence policy](../../docs/acceptance-evidence-policy.md),
this page is `source_review` evidence only: upstream documentation and release
metadata were read, but no command below has a native execution receipt on
macOS. `platform_profiles` entry `macos-arm64` in
[`adoption/manifest.json`](../manifest.json) has `status: drafted_not_accepted`
and `evidence_ref: null`. `adoption/manifest.json` `supported_platforms` stays
Linux/x86_64/Python 3.13 only; this profile does not change that. The `macos-arm64-foundation`
adoption profile lists the components this page assumes.

## Target hardware

Apple Silicon with **24 GB unified memory** as the default target, with a
**recorded 48 GB upgrade path** (below). Both sizes are candidates for a
first real qualification run; neither has one yet.

## Prerequisites

Homebrew, with the pins this profile assumes:

```sh
brew install git gh uv node@24 python@3.13 ripgrep jq coreutils restic shellcheck llama.cpp
```

Homebrew formulae float to whatever is current at install time. Record
`brew list --versions` in the host receipt (`evidence/receipts/adoption-<host>-<date>.json`,
schema in [`adoption/receipt.json`](../receipt.json)) immediately after this
step so the exact installed versions are retained, not just the formula names
above.

### darwin-arm64 pinned release archives

These components are installed from upstream `darwin-arm64` (or `darwin-arm64`-equivalent)
release archives rather than Homebrew, matching the archive convention in
[`recipes/README.md`](../../recipes/README.md#paths-pins-and-installation-conventions).
List only the upstream release asset name here; the publisher checksum/signature
and the resulting SHA-256 are recorded on the Mac at first install, in the host
receipt — not invented in this catalog:

| Component | Expected darwin-arm64 asset name pattern |
| --- | --- |
| `gh` | `gh_<version>_macOS_arm64.zip` |
| `uv` | `uv-aarch64-apple-darwin.tar.gz` |
| `gitleaks` | `gitleaks_<version>_darwin_arm64.tar.gz` |
| `syft` | `syft_<version>_darwin_arm64.tar.gz` |
| `dagu` | `dagu_<version>_darwin_arm64.tar.gz` |
| `qdrant` | `qdrant-aarch64-apple-darwin.tar.gz` |

## Embedding backend decision

**These are two separate embedding spaces by design, not two ports serving
the same model.** [The Linux/WSL2 profile](../../recipes/README.md#local-semantic-code-search)
runs `llama-server`/vLLM on **port 8231** serving **NVIDIA
Nemotron-3-Embed-1B-BF16** (2048 dimensions) as QMD's Qdrant-backed RAG
endpoint (`manifests/stack.json` records `"dimensions": 2048` for that
component; a real 2048-dim response from that host is recorded in
`evidence/artifacts/full-stack-convergence-20260921/embedding-result.json`).
Separately, QMD's own internal AST-chunk index model on that same Linux host
is `ggml-org/embeddinggemma-300M-GGUF` — a different model, not exposed on
8231, per that host's own `qmd status` output (`Embedding:
https://huggingface.co/ggml-org/embeddinggemma-300M-GGUF`, in
`evidence/receipts/native-token-ci-local-20260920.json`). Neither Linux model
is "the same 768-dim model QMD already uses" as a single fact; QMD's internal
index model is 768-ish-class embeddinggemma, the RAG endpoint at 8231 is the
2048-dim Nemotron.

**Default (24 GB): llama.cpp Metal**, `llama-server --embedding --port 8232`
(a distinct port from the canonical Linux RAG endpoint 8231, so a macOS host
never presents a 768-dim response where 2048-dim is expected) serving
**embeddinggemma-300M-Q8_0** (768 dimensions) — matching QMD's own internal
index model, not the Linux RAG endpoint's Nemotron model. This keeps QMD's
own index model identical across platforms; it does not claim parity with the
2048-dim Nemotron RAG endpoint, which macOS does not run in this default.

**Upgrade gate (48 GB): Nemotron-3-Embed-1B** (2048 dimensions, matching the
Linux RAG endpoint), **only if a GGUF build exists upstream** — this is an
open gate, not a scheduled step. If activated, it would run on its own port
(not 8231, which is a Linux-host loopback binding, not something a macOS host
shares) with its own qualification run.

**Overturn condition for the upgrade:** a measured retrieval comparison run on
this project's own corpus showing Nemotron beats embeddinggemma on
recall/MRR **and** the host has the memory headroom for it. Until that
comparison exists and passes both conditions, the 24 GB default stands even on
a 48 GB machine.

**Acceptance test for the 24 GB default (embeddinggemma-300M-Q8_0, 768
dimensions):**

```sh
curl 127.0.0.1:8232/v1/embeddings -d '{"model": "embeddinggemma-300M-Q8_0", "input": "<fixed test string>"}'
```

must return a 768-dimension vector, and its cosine similarity must be **≥
0.99** against a reference vector produced by running the same
embeddinggemma-300M-Q8_0 model through llama.cpp **on a Linux host** for the
same fixed string (not against the Linux profile's 2048-dim Nemotron
response, which is a different model and dimension and cannot be compared by
cosine similarity at all). No such Linux reference vector has been captured
and no such run has occurred on macOS; this is the test to run, not a result.
The 48 GB Nemotron upgrade, if ever activated, would instead compare against
the existing 2048-dim Linux Nemotron reference at 8231.

### Considered and not activated

- **MLX** — considered; not activated. No measured comparison against the
  llama.cpp Metal path exists yet on this project's retrieval workload.
- **LM Studio** — considered; not activated. The existing Linux profile's
  `EMBEDDING_PROVIDER=lmstudio` setting points at a local vLLM server, not the
  LM Studio desktop app; macOS would need its own separate evaluation before
  adoption, not an assumption that the Linux client setting transfers.
- **Docker Desktop** — not activated. **Apple Container** is the selected
  container runtime, for PostgreSQL only (mirrors the existing
  `apple-container` component scope in [`manifests/stack.json`](../../manifests/stack.json),
  Linux/WSL uses the direct native PostgreSQL recipe instead).

## launchd services

Linux/WSL2 uses `systemd --user`; macOS has no such manager. Table below
mirrors [`adoption/lifecycle.md`](../lifecycle.md#native-client-integration-and-process-lifecycle)'s
systemd table for the launchd equivalent — drafted, not run:

| systemd --user (Linux/WSL2) | launchd (macOS, drafted) |
| --- | --- |
| unit file under `~/.config/systemd/user/` | `~/Library/LaunchAgents/com.native-stack.{dagu,qdrant,ai-memory,otelcol}.plist` |
| `[Service] Restart=` | `KeepAlive` key |
| unit `Environment=` | `EnvironmentVariables` → `PATH` key inside the plist |
| journal / stdout redirection | logs written under `$STACK_HOME/state/logs` |
| `systemctl --user enable --now UNIT` | `launchctl bootstrap gui/$(id -u) <plist path>` |
| `systemctl --user restart UNIT` | `launchctl kickstart -k gui/$(id -u)/com.native-stack.<name>` |
| `systemctl --user is-active UNIT` | `launchctl print gui/$(id -u)/com.native-stack.<name>` |

Each plist needs `RunAtLoad` set and its own `EnvironmentVariables.PATH` entry
(macOS launchd agents do not inherit an interactive shell `PATH`). Retire a
launchd agent only with `launchctl bootout gui/$(id -u) <plist path>`,
mirroring the systemd `disable --now` rule: only if this qualification run
itself enabled it, and keep its data directories.

## Qdrant collections

Qdrant collections are **re-indexed on the new host, never copied** — the same
rule as [`adoption/lifecycle.md`](../lifecycle.md#stateful-persistence-and-recovery)'s
Qdrant row ("Native snapshot identity, isolated restored collection and actual
retrieval; copying binary files alone is not state recovery"). A macOS host
starts from an empty Qdrant instance and reruns the project index, it does not
receive a copied `storage/` directory from the Linux host.

## GPU / no-GPU

Apple Silicon has Metal available on every target machine in this profile, so
there is no true "no-GPU" macOS case in scope; the fallback path is the
**smaller model on CPU** (embeddinggemma on CPU) if Metal is unavailable in a
given execution context (for example, a sandboxed CI runner), not a switch to
a different backend.

## Must be re-established on macOS

These are Linux/WSL-specific and have no macOS equivalent; each is a fresh
qualification on this platform, not a port:

- `sandbox-runtime` (bwrap-based namespace isolation) — no bwrap on macOS.
- Every WSL-only path in [`adoption/lifecycle.md`](../lifecycle.md) and
  [`docs/portable-userspace-install-20260921.md`](../../docs/portable-userspace-install-20260921.md)
  (the existing WSL kernel, Windows-mount `PATH` segments, and the WSL vLLM
  0.25.0 GPU pin documented in [the Linux/WSL2 page](linux-wsl2.md)).
- Every native sign-in, service start, and acceptance test named above.
