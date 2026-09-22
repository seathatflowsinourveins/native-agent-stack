# **Drafted, not accepted — nothing on this page was executed on a Mac workstation**

Per [the acceptance evidence policy](../../docs/acceptance-evidence-policy.md),
this page is `source_review` evidence plus one hosted-runner execution: upstream
documentation and release metadata were read, and the bootstrap script has a
native execution receipt from a GitHub-hosted macOS arm64 runner
([`evidence/receipts/adoption-macos-hosted-smoke-20260922.json`](../../evidence/receipts/adoption-macos-hosted-smoke-20260922.json),
"What a hosted run proves" below), but no command below has an execution receipt
from a Mac workstation. `platform_profiles` entry `macos-arm64` in
[`adoption/manifest.json`](../manifest.json) has `status: drafted_not_accepted`
and `evidence_ref: null`. `adoption/manifest.json` `supported_platforms` stays
Linux/x86_64/Python 3.13 only; this profile does not change that. The `macos-arm64-foundation`
adoption profile lists the components this page assumes.

## Target hardware

Apple Silicon with **24 GB unified memory** as the default target, with a
**recorded 48 GB upgrade path** (below). Both sizes are candidates for a
first real qualification run; neither has one yet.

## Prerequisites

Homebrew, for the formulae this profile still leaves floating:

```sh
brew install jq python@3.13 ripgrep coreutils restic shellcheck
```

`brew install python@3.13` is not optional: a fresh Mac's `python3` is **3.9**
from the Command Line Tools, below the Python 3.13 the `acceptance_target` in
[`adoption/manifest.json`](../manifest.json) requires, and macOS ships no
system Python that can satisfy it.

`node`, `uv`, `gh`, `llama.cpp` and Qdrant are **no longer Homebrew formulae**
in this draft: they are SHA-256 pinned upstream release archives installed by
[`adoption/bootstrap-macos.sh`](../bootstrap-macos.sh) from
[`adoption/pins-macos-arm64.json`](../pins-macos-arm64.json), so their versions
match the Linux profile instead of floating with the tap.

Homebrew formulae that remain float to whatever is current at install time. The
bootstrap records `brew list --versions` into
`$ECO_INSTALL_ROOT/installed-versions.txt`; copy it into the host receipt
(`evidence/receipts/adoption-<host>-<date>.json`, schema in
[`adoption/receipt.json`](../receipt.json)) so the exact installed versions are
retained, not just the formula names above.

The script keeps to what a stock Mac has: `shasum -a 256` instead of
`sha256sum`, an atomic `mkdir` lock instead of `flock`, `cd` + `pwd -P` instead
of `realpath`, and no bash-4-only syntax, because `/bin/bash` on macOS is 3.2.

The lock is `$ECO_INSTALL_ROOT/bootstrap.lock.d` (default
`$HOME/.local/share/codex-ecosystem/bootstrap.lock.d`). A run removes it on
exit, including on a failure, and only when that run created it — but a
`SIGKILL`ed or power-cut run leaves it behind, and every later run then exits 1
with `Another ecosystem bootstrap is running`. Recovery: confirm no bootstrap is
running (`pgrep -fl bootstrap-macos.sh` prints nothing), then remove the stale
lock directory before retrying:

```sh
pgrep -fl bootstrap-macos.sh || rmdir "${ECO_INSTALL_ROOT:-$HOME/.local/share/codex-ecosystem}/bootstrap.lock.d"
```

### Bootstrap usage and exit codes

```sh
bash adoption/bootstrap-macos.sh --profile macos-arm64-foundation \
  [--skip-system-packages] [--allow-unpinned <id,id,...>] [--plan]
```

`--plan` resolves and prints every pinned component (version, asset, SHA-256)
with no network access and no installation. On this repository's Linux host it
runs only under a `uname`/`sw_vers` shim. The full install path (no `--plan`,
with `--skip-system-packages`) has run on real Darwin arm64 once, on the hosted
runner described in "What a hosted run proves" below; every workstation step on
this page — Homebrew prerequisites, sign-in, launchd, the embedding
acceptance — remains unrun.

| Exit | Meaning |
| --- | --- |
| 0 | The profile installed, or `--plan` finished printing it. |
| 1 | Guard or refusal: not Darwin/arm64, run as root, no Homebrew for a real run, an unusable `ECO_INSTALL_ROOT`, another bootstrap holding the lock, a checksum mismatch, or a pin whose `sha256` is null (fail closed, in `--plan` too). |
| 2 | Usage error: missing `--profile`, an unknown argument, or a flag given without its value. |
| 3 | A selected component has no pin at all in [`adoption/pins-macos-arm64.json`](../pins-macos-arm64.json) and was not named in `--allow-unpinned`. Checked before anything is installed, and in `--plan` too; `--allow-unpinned <id,id,...>` skips the named ids instead and echoes them to the run log. |
| 4 | A prerequisite (`curl`, `git`, `tar`, `shasum`, `unzip`, `jq`, `mktemp`) is still missing after the Homebrew step. With `--skip-system-packages` no `brew install` is attempted and the check lists what is missing. |

`socraticode` is the one selected component this draft leaves unpinned (below);
the script carries it as a documented skip, so the shipped profile needs no
`--allow-unpinned`. Exit codes 3 and 4 and the `--allow-unpinned` flag mirror
[`adoption/bootstrap-linux.sh`](../bootstrap-linux.sh). Two differences are
disclosed rather than hidden: this script carries
`documented_unpinned_ids=(socraticode)`, a built-in skip list the Linux script
does not have, so an unpinned `socraticode` never trips the exit-3 refusal here;
and `--plan` is macOS-only.

### darwin-arm64 pinned release archives

These components are installed from upstream `darwin-arm64` (or `darwin-arm64`-equivalent)
release archives rather than Homebrew, matching the archive convention in
[`recipes/README.md`](../../recipes/README.md#paths-pins-and-installation-conventions).
Every SHA-256 below was read from the publisher on 2026-09-22 — a checksum file,
a `.sha256` sidecar, or (where the publisher ships neither) the GitHub release
asset `digest` plus an independent re-hash of the downloaded asset. None was
guessed, and none was produced on a Mac: reading a publisher checksum is
`source_review`/independent observation, not an installation receipt. The
machine-readable copy with each `checksum_source` and `checksum_ref` is
[`adoption/pins-macos-arm64.json`](../pins-macos-arm64.json).

| Component | Version | Asset | SHA-256 | checksum_source |
| --- | --- | --- | --- | --- |
| `node` | 24.21.0 | `node-v24.21.0-darwin-arm64.tar.xz` | `6239d4cf92d864487ec8cd3615038f7b67e7f58b77b21cd2f09ea9fbd68065fe` | `publisher_checksum_file` |
| `uv` | 0.12.17 | `uv-aarch64-apple-darwin.tar.gz` | `85f00cbdc6dd3e97eba4c31b4d014375a9fdfe8f570023b84e5102fc3456896b` | `publisher_checksum_sidecar` |
| `gh` | 2.101.0 | `gh_2.101.0_macOS_arm64.zip` | `e4303e39d8f07141c4bad4b99b01079f05029c59b27076e8fbc825c985ecdd8b` | `publisher_checksum_file` |
| `codex` | 0.155.1 | `codex-0.155.1.tgz` | `fded5b71797aaaf9b1c3229c0e2747b53b39887ef25f36ec7196f6d511db1a66` | `npm_registry_integrity_crosscheck` |
| `claude-code` | 2.1.278 | `claude-code-2.1.278.tgz` | `08c6dfcf3dafcfd30e09b2926c596e274f0fa20844a5801ada7f1c8e6227157e` | `npm_registry_integrity_crosscheck` |
| `mcporter` | 0.13.13 | `mcporter-0.13.13.tgz` | `ccab169473a3f863fcadf833eff5023f40eb8600dcfe3b7b92678d876765601d` | `npm_registry_integrity_crosscheck` |
| `context-mode` | 1.0.169 | `context-mode-1.0.169.tgz` | `09c41e4cf77b21566c76b8ea2fdbd7f3d823055fee2f02c2166fd5bb575daf2c` | `npm_registry_integrity_crosscheck` |
| `ai-memory` | 2.3.2 | `ai-memory-macos-aarch64.tar.gz` | `e0f07ad28938f3ed98a5feb21d11917245d77501764e0005049e7d9c1c16f28a` | `publisher_checksum_sidecar` |
| `llama-cpp` | b11057 | `llama-b11057-bin-macos-arm64.tar.gz` | `443eadead90d44c3925b7163012430b2df4934df881cf72a4d94fc71d1380da1` | `github_release_asset_digest_plus_local_rehash` |
| `qdrant` | 1.19.1 | `qdrant-aarch64-apple-darwin.tar.gz` | `e060209dfefc9d977ddcec48521349f505f8fd1ce21f2a3db444140870522fe4` | `github_release_asset_digest_plus_local_rehash` |

Not pinned here: `socraticode` (no darwin-arm64 release archive reviewed for
this draft — it is skipped by the bootstrap with a printed note and is not a
`required_command` of the profile), and `gitleaks`, `syft` and `dagu`, which
are not in the `macos-arm64-foundation` component list.

Two pins are only partly covered by their hash. The `@openai/codex` and
`@anthropic-ai/claude-code` npm tarballs are byte-identical to the Linux pins,
but on Apple Silicon npm additionally resolves `@openai/codex-darwin-arm64` and
`@anthropic-ai/claude-code-darwin-arm64` — the packages carrying the real
binaries — **unpinned** at install time. Record their resolved versions and
integrity from the host's `npm ls` output at first install.

`llama-server` is a profile `required_command`, so llama.cpp is pinned rather
than left to `brew install llama.cpp`. The macOS asset holds every executable
in one flat directory **beside its dylibs** (observed with `tar -tzf`; there is
no `build/bin` path in this asset), so the bootstrap installs the whole
directory into `tools/llama-cpp-b11057` and places a wrapper script at
`bin/llama-server` that exports `DYLD_LIBRARY_PATH` before exec'ing the real
binary, instead of a bare symlink.

## What a hosted run proves

The `platform_profiles` row for `macos-arm64` names a hosted smoke job
(`.github/workflows/adoption-bootstrap.yml`, job `bootstrap-macos`) whose status
is `green_on_hosted_runner`. It has run green twice: run `35753384567` at head
`585032a` (the macOS job passed; that run's `validate` job failed for an
unrelated ShellCheck code), and run `35753801691` at head `9d9ce2b` (job
`106834376649`, runner label `macos-15`, GitHub-hosted image provisioner
`20260828.587`, macOS 15.7.9 build 24G830, Python 3.13.15), which is the run
recorded in
[`evidence/receipts/adoption-macos-hosted-smoke-20260922.json`](../../evidence/receipts/adoption-macos-hosted-smoke-20260922.json).
Its bounded claim is native operation of this script on a **GitHub-hosted macOS
arm64 runner** — that the pinned assets download, verify against these
SHA-256 values, extract and report versions on Apple Silicon.
That is not a workstation acceptance:

- A hosted runner is not this profile's target Mac; hardware, memory (24/48 GB),
  installed Homebrew state and the user's own account are all different.
- launchd remains unrun. No agent in the table below has been bootstrapped,
  kickstarted or booted out on any Mac, hosted or otherwise.
- The embedding acceptance below (port 8232, 768-dimension response, ≥ 0.99
  cosine against a Linux reference vector) remains unrun, and a sandboxed
  runner is exactly the context where Metal may be unavailable.
- Native sign-in for Codex, Claude and GitHub cannot happen on a hosted runner.

Until a real Mac produces a receipt, this profile stays
`status: drafted_not_accepted` with `evidence_ref: null`.

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
