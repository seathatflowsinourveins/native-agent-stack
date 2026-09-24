# **Drafted, not accepted — nothing on this page was executed on a Mac workstation**

Per [the acceptance evidence policy](../../docs/acceptance-evidence-policy.md),
this page is `source_review` evidence plus one hosted-runner execution: upstream
documentation and release metadata were read, and the bootstrap script has a
native execution receipt from a GitHub-hosted macOS arm64 runner
([`evidence/receipts/adoption-macos-hosted-smoke-20260923.json`](../../evidence/receipts/adoption-macos-hosted-smoke-20260923.json):
launchd agents, the embedding acceptance against the Linux reference vector,
and the recording smoke; earlier
[`adoption-macos-hosted-smoke-20260922.json`](../../evidence/receipts/adoption-macos-hosted-smoke-20260922.json);
"What a hosted run proves" below), but no command below has an execution receipt
from a Mac workstation. `platform_profiles` entry `macos-arm64` in
[`adoption/manifest.json`](../manifest.json) has `status: drafted_not_accepted`
and `evidence_ref: null`. `adoption/manifest.json` `supported_platforms` stays
Linux/x86_64/Python 3.13 only; this profile does not change that. The `macos-arm64-foundation`
adoption profile lists the components this page assumes.

## Get the catalog

Clone the catalog and check out its attested release tag before any step
below ([`adoption/bootstrap.md`](../bootstrap.md) step 0 has the detail,
including `gh attestation verify` for a downloaded release archive). A fresh
Mac's `/usr/bin/python3` is 3.9 from the Command Line Tools; that is enough for
these one-liners and `scripts/release_due.py`.

```sh
git clone https://github.com/seathatflowsinourveins/native-agent-stack.git
cd native-agent-stack
python3 scripts/release_due.py   # on the default branch (added after v2026.09.23): steps main documents that the pinned release lacks
tag="$(python3 -c "import json;print(json.load(open('adoption/manifest.json'))['source']['release_tag'])")"
commit="$(python3 -c "import json;print(json.load(open('adoption/manifest.json'))['source']['release_commit'])")"
git checkout "$tag"
if test "$(git rev-parse HEAD)" = "$commit"; then echo "at $tag ($commit)"; else echo "error: $tag is not the pinned release commit $commit" >&2; false; fi
```

Read both values before the checkout, as above: the release's own manifest
names the release before it. `scripts/release_due.py` was added after
`v2026.09.23`, so it runs on the default branch.

This page describes main, and much of the macOS install path is newer than
`v2026.09.23`. A section whose file release `vT` lacks says "added after
`vT`"; one whose file exists at `vT` but behaves differently there says
"changed after `vT`" and states the difference. If your checkout is `vT`,
follow the note: run an "added after" step from a separate clone of the
default branch (never the pinned one you install from; a result from it is
main-only evidence), or wait for the next re-pin. If your checkout is a later
release, the note is history and the step is in your checkout (`test -e
<path>` confirms).

## Ordered steps for a new macOS host

1. Prerequisites and target hardware (the next two sections), then
   `python3 scripts/hardware_profile.py` to measure this Mac against
   [`adoption/hardware-profiles.json`](../hardware-profiles.json).
2. `bash adoption/bootstrap-macos.sh --profile macos-arm64-foundation`
   (usage and exit codes below). Use `macos-arm64-foundation`, not
   `foundation-cpu`: `qmd` and `rtk` have no macOS pin, so `foundation-cpu`
   exits 3 here. The script and `adoption/pins-macos-arm64.json` changed after
   `v2026.09.23`: at that tag the script installs only a missing `jq` through
   Homebrew, so run the `brew install` line under "Prerequisites" yourself
   first, and it skips `socraticode` (no pin there), installing 7 of the 8
   components; install `socraticode` through its recipe.
3. Native sign-in and config rendering: [`adoption/bootstrap.md`](../bootstrap.md)
   steps 3–4 (Codex, Claude and GitHub device flows; `tools/adoption/render_config.py`
   with this host's own `adoption/hosts/<host>.json`).
4. launchd services and the embedding acceptance ("launchd services" and
   "Embedding backend decision" below). `adoption/launchd/launchd-agents.sh`
   and `tools/adoption/embed_acceptance.py` were added after `v2026.09.23`, and
   so were their inputs: at that tag `bootstrap-macos.sh` neither downloads the
   embedding model (`models[0]` in main's darwin pins) into `state/models` nor
   writes `config/qdrant.yaml`, which the qdrant and llama-embed agents need.
   **Until main is re-pinned to a release that contains the macOS clean install
   (#94), run this page from step 2 onward from a default-branch clone** and
   record the receipts with that clone's `catalog_revision` (main-only
   evidence, labelled as such).
5. `uv run --no-project --python 3.13 python scripts/adoption_status.py --profile macos-arm64-foundation --json`
   (changed after `v2026.09.23.1`, which runs plain `python3`; the manifest supports
   Python 3.13 only, so run this form there too),
   then the per-host receipt ([`adoption/bootstrap.md`](../bootstrap.md) steps 6–7).
6. Contribute what ran: record host receipts with `scripts/host_receipts.py`
   (`--platform-id macos-arm64`, and `--second-physical-machine` on a real Mac
   workstation) from a branch of current `main`, refresh the generated matrix
   and grand list, and open a PR, following
   [`docs/contributing-evidence.md`](../../docs/contributing-evidence.md).
7. When a newer release is pinned, follow
   [moving a host to a new release](../update.md#moving-a-host-to-a-new-release).

## Target hardware

Apple Silicon with **24 GB unified memory** as the default target, with a
**recorded 48 GB upgrade path** (below) that also covers larger machines. The
64 GB Mac that [`docs/next-host-stages.md`](../../docs/next-host-stages.md)
plans for is the labelled projection `macos-arm64-64gb-projected` in
[`adoption/hardware-profiles.json`](../hardware-profiles.json) (about 38 GB of
unified memory as the generation budget, `full` semantic-RAG tier, both drawn
from one shared pool); for this page's embedding choice it follows the 48 GB
rules. None of these sizes has a real qualification run yet.

## Prerequisites

Homebrew, for six formulae this profile still leaves floating: jq,
python@3.13, ripgrep, coreutils, restic and shellcheck. On main,
[`adoption/bootstrap-macos.sh`](../bootstrap-macos.sh) installs these itself
(the equivalent of running the command below), one `brew list --versions
<formula>` check per formula, installing only the ones actually missing —
manually running it first is no longer required, only still possible. That
changed after `v2026.09.23`: the script at that tag installs only a missing
`jq`, so at that tag run this command yourself before the bootstrap:

```sh
brew install jq python@3.13 ripgrep coreutils restic shellcheck
```

`brew install python@3.13` (part of the formula list above) is not optional:
a fresh Mac's `python3` is **3.9** from the Command Line Tools, below the
Python 3.13 the `acceptance_target` in [`adoption/manifest.json`](../manifest.json)
requires, and macOS ships no system Python that can satisfy it.

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

On main every selected `macos-arm64-foundation` component, including
`socraticode` (below), has a pin, so the shipped profile needs no
`--allow-unpinned`. The script and pins changed after `v2026.09.23`: at that
tag `socraticode` has no pin and the script skips it by default
(`documented_unpinned_ids=(socraticode)`), so the profile exits 0 with 7 of 8
components installed and `socraticode` left to its recipe.
Exit codes 3 and 4 and the `--allow-unpinned` flag mirror
[`adoption/bootstrap-linux.sh`](../bootstrap-linux.sh). One difference is
disclosed rather than hidden: the script keeps a `documented_unpinned_ids=()`
mechanism the Linux script does not have — a built-in skip list, currently
empty, so a future undocumented gap still trips the exit-3 refusal instead of
silently reusing a stale skip; `--plan` is also macOS-only.

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
| `claude-code` | 2.1.281 | `darwin-arm64/claude` (native, not npm) | `a922981f6f3b55a251ef9f9dbaa0621a5f99cbcb5ca67f8a797476ccfc83f626` | `manifest_crosscheck` |
| `mcporter` | 0.13.13 | `mcporter-0.13.13.tgz` | `ccab169473a3f863fcadf833eff5023f40eb8600dcfe3b7b92678d876765601d` | `npm_registry_integrity_crosscheck` |
| `context-mode` | 1.0.169 | `context-mode-1.0.169.tgz` | `09c41e4cf77b21566c76b8ea2fdbd7f3d823055fee2f02c2166fd5bb575daf2c` | `npm_registry_integrity_crosscheck` |
| `ai-memory` | 2.3.2 | `ai-memory-macos-aarch64.tar.gz` | `e0f07ad28938f3ed98a5feb21d11917245d77501764e0005049e7d9c1c16f28a` | `publisher_checksum_sidecar` |
| `llama-cpp` | b11057 | `llama-b11057-bin-macos-arm64.tar.gz` | `443eadead90d44c3925b7163012430b2df4934df881cf72a4d94fc71d1380da1` | `github_release_asset_digest_plus_local_rehash` |
| `qdrant` | 1.19.1 | `qdrant-aarch64-apple-darwin.tar.gz` | `e060209dfefc9d977ddcec48521349f505f8fd1ce21f2a3db444140870522fe4` | `github_release_asset_digest_plus_local_rehash` |
| `socraticode` | 1.14.0 | `socraticode-1.14.0.tgz` | `3dbb106c876be4214048289cef31094eb0e48e97007fb90180270edc4eed7c46` | `npm_registry_integrity_crosscheck` |

`socraticode` is installed with `--ignore-scripts` (the pin's own
`ignore_scripts: true` field, read by the script's `install_npm`), the same
convention [`recipes/README.md`](../../recipes/README.md#paths-pins-and-installation-conventions)
documents for the Linux recipe; it has no `adoption/pins-linux-x86_64.json`
entry of its own there, only that documented manual recipe. The `socraticode`
row, both `platform_dependency` pins below and the `models[0]` embedding-model
pin were added to `adoption/pins-macos-arm64.json`, which changed after
`v2026.09.23`: at that tag npm resolves the Codex and Claude Code darwin
binaries unverified and the embedding model is not downloaded by the
bootstrap. Not in this table:
`gitleaks`, `syft` and `dagu`, which are not in the `macos-arm64-foundation`
component list.

One pin, `codex`, still carries an additional `platform_dependency`, not
covered by the hash above. The `@openai/codex` npm tarball is byte-identical
to the Linux pin, but on Apple Silicon npm additionally resolves
`@openai/codex-darwin-arm64` — the package carrying the real binary. A `npm
install` of the wrapper alone auto-fetches this platform package too,
unverified (measured directly: `--omit=optional`, `--no-optional` and
`NPM_CONFIG_OMIT=optional` do not suppress it, and this install path has no
lockfile to omit from in the first place). `adoption/bootstrap-macos.sh`'s
`install_platform_dependency` does not trust that fetch or try to read it
back: the pin instead records the platform package's own `name`,
`resolved_package`, `version` and independent `sha256`, and the function (1)
installs the wrapper with `--ignore-scripts`, deferring its lifecycle
scripts; (2) asks Node's own `require.resolve`, scoped to the wrapper's
directory, exactly where it would resolve this dependency from, trusting and
deleting that path only when it is an EXACT canonicalized-path match for the
one nested location the wrapper's own `node_modules` would use (never
whatever `require.resolve`'s NODE_PATH/GLOBAL_FOLDERS fallback might report
from outside the prefix entirely) — falling back to a top-level alias inside
the prefix otherwise; (3) extracts the independently sha256-verified tarball
there instead; (4) re-verifies resolution, the resolved package.json's
`version` against the pin, and its `name` against `resolved_package`, fail
closed (exit 1) on any mismatch; and (5) runs `npm rebuild` for the wrapper
so its deferred lifecycle scripts run against the now-verified copy. Every
path this compares is canonicalized first (`canonical_path`, in the script),
because Node realpath-resolves symlinks by default when it locates a module
and a real Mac's `/var` is a symlink to `/private/var`. `@openai/codex-darwin-arm64`
is not itself a published package name: `npm view @openai/codex@0.155.1
optionalDependencies` shows it as an `npm:` alias to
`@openai/codex@0.155.1-darwin-arm64`, the same `@openai/codex` package name
at a platform-suffixed version, and the pin's `resolved_package`/`version`
fields record that distinction.

**2026-09-23: `claude-code` moved off this npm + `platform_dependency` +
postinstall-copy design entirely.** It is now a `kind: native` pin (see the
table above): `adoption/bootstrap-macos.sh`'s `install_native` downloads the
per-version `darwin-arm64/claude` binary directly from
`downloads.claude.ai`, verifies its sha256 against the pin, and runs `"$bin"
install 2.1.281`, exactly mirroring `adoption/pins-linux-x86_64.json`'s own
`claude-code` pin and `~/codex-ecosystem/bin/bootstrap-linux.sh`'s
existing claude-code step. There is no more nested platform package, no
`install.cjs` postinstall to defer, and no `postinstall_binary_check`; the
native binary manages its own version directory and launcher and keeps
auto-updating on the latest channel afterward. Both claude-code pins
(this page's and `adoption/pins-linux-x86_64.json`'s) changed after `v2026.09.23`;
at that tag they are npm pins.

The pin is a floor: when `~/.local/bin/claude --version` already reports the
pinned version or newer, `install_native` keeps that launcher, downloads and
installs nothing, and logs `Kept installed claude-code <version>`; only a
missing, older or unreadable launcher gets the verified install, so re-running
the bootstrap never moves a native auto-updated Claude Code back to the pin
(`adoption/bootstrap-linux.sh` runs the same `install_native`).
The script and both claude-code pins (2.1.281, which fixes a recursive `rm` of
command-substitution output running unprompted in auto and bypass mode)
changed after `v2026.09.24.1`: at that tag the pins are 2.1.280 and the script
runs the pinned install unconditionally, downgrading a newer Claude Code.

`llama-server` is a profile `required_command`, so llama.cpp is pinned rather
than left to `brew install llama.cpp`. The macOS asset holds every executable
in one flat directory **beside its dylibs** (observed with `tar -tzf`; there is
no `build/bin` path in this asset), so the bootstrap installs the whole
directory into `tools/llama-cpp-b11057` and places a wrapper script at
`bin/llama-server` that exports `DYLD_LIBRARY_PATH` before exec'ing the real
binary, instead of a bare symlink.

## What a hosted run proves

The `platform_profiles` row for `macos-arm64` names a hosted smoke job
(`.github/workflows/adoption-bootstrap.yml`, jobs `bootstrap-macos`,
`bootstrap-macos-brew` and `validate-macos`) whose status is
`green_on_hosted_runner`. The current run is **`35875188590`** at head
`75a6e0d` (PR #94, `workflow_dispatch`, runner label `macos-15`, macOS
15.7.9 build 24G830), every job green, recorded in
[`evidence/receipts/adoption-macos-hosted-smoke-20260923.json`](../../evidence/receipts/adoption-macos-hosted-smoke-20260923.json).
That run and its receipt were added after `v2026.09.23`: they exercise the
#94 script and pins, not the ones in that tag.
Earlier runs (`35753384567`/`585032a`, `35753801691`/`9d9ce2b`, both
recorded in the retired 2026-09-22 receipt) predate the round-3g through
3i redesign covered here and are superseded by this one; they are not
cited further below.

This run's bounded claim is still hosted-runner evidence,
**not a workstation acceptance**:

- `bootstrap-macos`: `adoption/bootstrap-macos.sh --profile
  macos-arm64-foundation` installed the full pinned `darwin-arm64` set
  into a disposable `ECO_INSTALL_ROOT`, including the pinned
  `embeddinggemma-300M-Q8_0` model (sha256 checked) and a provisioned
  `config/qdrant.yaml` (round 3j).
- **launchd genuinely ran**, for the first time: `launchd-agents.sh`
  rendered, linted, bootstrapped and booted out both the `qdrant` and
  `llama-embed` LaunchAgents on this runner. `qdrant` reported health
  version `1.19.1`. This is still bounded to the runner's own GUI domain
  for the duration of one job -- persistence across logins, reboots and
  real user sessions was not observed, and it is not evidence for any
  other Mac.
- **The embedding acceptance ran and passed**: dimension 768, cosine
  **0.99944** against the Linux CPU reference vector
  (`evidence/artifacts/macos-embed-reference-20260923/`), threshold 0.99.
  The `llama-server` startup log itself reports `layer 0 is assigned to
  device MTL0 but Flash Attention is assigned to device CPU` -- **Metal
  device `MTL0` did engage** on this specific hosted run, for the layers
  it covers, with flash attention still on CPU. This is one hosted run's
  own log line, not a claim that every hosted run (or every real Mac)
  engages Metal identically, and it is still bounded to whatever GPU a
  GitHub-hosted macOS runner happens to expose that day, not a real
  Mac's own dedicated GPU under real load.
- `bootstrap-macos-brew`: the Homebrew prerequisite path (installing the
  six floating formulae without `--skip-system-packages`) completed.
- `validate-macos`: every validator, the adoption test modules (238
  tests, `OK`), and (round 3i) a real `host_receipts.py record`/
  `validate`/`component_matrix`/`new_host_grand_list` recording smoke in
  a throwaway checkout copy all passed -- **on both `actions/setup-python`
  3.13.15 and the runner's own system `/usr/bin/python3` 3.9.6**, the
  exact two-interpreter claim "Recording and verdict scripts" above
  describes. On that run the full `python3 -m unittest`, then non-gating,
  ran 2929 tests with 29 failures and 95 errors. Most came from macOS's
  symlinked temp directories (`/var/folders`, `/tmp` resolving to
  `/private/...`) tripping repository path-containment checks, plus
  Linux-only tests not skipped on macOS. PR #126 fixed them: a shared
  `scripts/path_safety.py` tolerates only root-owned links directly under
  `/`, and platform-specific tests are skipped where they do not apply.
  Hosted run 35898879109 then passed the full suite on macos-15 (3156
  tests, `OK`, skipped=435), and the full suite is now a **gating** step
  of `validate-macos`. This is still hosted-runner evidence, not a Mac
  workstation.

Still bounded, exactly as before:

- A hosted runner is not this profile's target Mac; hardware, memory (24/48 GB),
  installed Homebrew state and the user's own account are all different.
- Native sign-in for Codex, Claude and GitHub cannot happen on a hosted runner.
- No `macos-arm64` `platform_status` is changed by this receipt (the
  matrix/verdict machinery this same run's `validate-macos` job now gates
  on requires a receipt with `host.second_physical_machine: true` plus an
  independent, non-self review -- neither of which a hosted runner can
  ever provide by construction).

Until a real Mac produces a receipt, this profile stays
`status: drafted_not_accepted` with `evidence_ref: null`.

## Recording and verdict scripts

A 2026-09-23 peer-update-audit gap (`adoption_macos`, medium): the catalog's
own recording and verdict scripts (`scripts/host_receipts.py`,
`scripts/component_matrix.py`, `scripts/new_host_grand_list.py`,
`tools/sota-convergence/build_verdicts.py`, `scripts/validate_convergence.py`,
`scripts/release_due.py`) had never actually run on macOS CI or against
macOS's own system Python -- every existing gating job for them
(`.github/workflows/validate.yml`, `.github/workflows/catalog-freshness.yml`)
runs on `ubuntu-24.04` only. A future macOS host recording evidence with
these exact scripts, on macOS's own BSD userland and system `git`, was
entirely unexercised.

Fixed (round 3i): `adoption-bootstrap.yml`'s `validate-macos` job (`macos-15`)
now runs all six scripts as gating checks, then a **recording smoke**: it
installs this profile (the same bootstrap step `bootstrap-macos` runs),
records a real `host_receipts.py record` receipt for a cheap, already-
installed component (`codex`, `--from-stack-commands`, `--evidence-class
native_proven` -- a green hosted job is real execution for exactly what it
ran, never a workstation acceptance receipt; see "What a hosted run proves"
above) inside a **throwaway copy** of the checkout (`$RUNNER_TEMP/rec`, never
the real one, so nothing is ever committed from this step), then re-runs
`host_receipts.py validate`, `component_matrix.py --write`, then
`component_matrix.py --check`, and `new_host_grand_list.py --write`, then
`new_host_grand_list.py --check` (separate invocations: `--write` and
`--check` are mutually exclusive) in that same copy. This proves the
recording path works under macOS Python, BSD userland and the system `git`,
never that this ONE receipt establishes any platform-status change (it does
not carry `second_physical_machine: true`, and it is discarded with the
throwaway copy at the end of the job).

**Minimum Python version: 3.9**, declared in
[`adoption/bootstrap.md`](../bootstrap.md) and tested directly, not merely
declared: the recording smoke above runs once against the manifest-pinned
Python line (`python@3.13` via `actions/setup-python`) and once against the
runner's own **system** `/usr/bin/python3` (macOS ships 3.9.6 there by
default on every macOS 15 image observed so far, which is exactly this
floor -- a version this project's own bootstrap already flags as below the
`python@3.13` this profile's prerequisites require, in "Prerequisites"
above). If a runner's system Python were ever below 3.9, that second run is
skipped with a message rather than failing the job; the CI log states
whichever happened. This is still hosted-runner evidence, not a workstation
observation: it establishes that these scripts run under a real macOS
Python 3.9 interpreter as installed by Apple on this runner image, not that
every real Mac's system Python matches it forever.

`scripts/release_due.py` was added after `v2026.09.23`; that does not block a
host, because recording runs on a branch of current `main`
([`docs/contributing-evidence.md`](../../docs/contributing-evidence.md) step 1)
and step 0 runs the check on the default branch before the checkout.

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
cosine similarity at all). The 48 GB Nemotron upgrade, if ever activated,
would instead compare against the existing 2048-dim Linux Nemotron
reference at 8231.

**The Linux reference vector now exists** (2026-09-23):
[`evidence/artifacts/macos-embed-reference-20260923/macos-embed-reference-20260923.json`](../../evidence/artifacts/macos-embed-reference-20260923/macos-embed-reference-20260923.json)
-- llama.cpp b11057 (commit `59657a613`), the `ubuntu-x64` CPU build, running
the identical pinned `embeddinggemma-300M-Q8_0.gguf`
(`adoption/pins-macos-arm64.json`'s own `models[0]`, same sha256), captured
against the exact request body this reference records, L2-normalized,
repeat cosine 1.0 (i.e. the same request run twice against the same model
returns the identical vector, establishing the comparison itself is
deterministic before ever comparing across hosts). This is a Linux-side
capture, never a macOS observation, and it does not by itself establish
what a real Mac's Metal backend would return. The one command a real Mac
(or the hosted CI step below) runs against a live `llama-server` on port
8232 is (`tools/adoption/embed_acceptance.py` and this reference vector were
added after `v2026.09.23`; at that tag run it from a default-branch clone):

```sh
python3 tools/adoption/embed_acceptance.py http://127.0.0.1:8232 \
  evidence/artifacts/macos-embed-reference-20260923/macos-embed-reference-20260923.json
```

It sends the reference's own exact request body, checks the response's
dimension and its cosine similarity against the reference's own embedding,
and prints a JSON result (`"passed": true`/`false`, the actual cosine, and
which backend to record separately from `llama-server`'s own startup log --
this script cannot itself tell Metal from CPU). Exit 0 on a pass, 1
otherwise, in both cases with the numbers in the JSON, never a bare
pass/fail with nothing to inspect.

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
systemd table for the launchd equivalent — drafted, not run on a Mac workstation:

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

Templates for the three agents this profile's components need — Qdrant,
ai-memory, and the llama.cpp Metal embedding server — are drafted at
[`adoption/launchd/com.native-stack.qdrant.plist.template`](../launchd/com.native-stack.qdrant.plist.template),
[`adoption/launchd/com.native-stack.ai-memory.plist.template`](../launchd/com.native-stack.ai-memory.plist.template)
and
[`adoption/launchd/com.native-stack.llama-embed.plist.template`](../launchd/com.native-stack.llama-embed.plist.template),
using the same `${NAME}` placeholder convention as
[`adoption/templates/`](../templates/)'s Claude/Codex configs. Render them
with [`tools/adoption/render_launchd.py`](../../tools/adoption/render_launchd.py)
(`--host <name>` against an `adoption/hosts/<name>.json` value file such as
[`adoption/hosts/macos-example.json`](../hosts/macos-example.json), or
`--set KEY=VALUE`), and drive the rendered plists with
[`adoption/launchd/launchd-agents.sh`](../launchd/launchd-agents.sh)'s five
subcommands: `render`, `lint` (`plutil -lint`, or a `plistlib` fallback where
`plutil` is unavailable), `install` (stage, lint, bootout the label if it is
currently loaded from that same destination path, rename into place,
`launchctl enable` + `launchctl bootstrap`), `status` (`launchctl print`) and
`remove` (bootout, then delete the plist, again only ever acting on a label
confirmed loaded from its own destination path, or not loaded at all with a
file present to clean up). On the hosted runner (run `35875188590`, "What a
hosted run proves" above) `launchd-agents.sh` bootstrapped and booted out the
`qdrant` and `llama-embed` agents; `ai-memory` has not run, and none of the
three has run on a Mac workstation.

**Added after `v2026.09.23`.** The three templates, `launchd-agents.sh`,
`tools/adoption/render_launchd.py`, `adoption/hosts/macos-example.json` and
`tests/test_adoption_launchd.py` are not in that tag (`python3
scripts/release_due.py` on the default branch lists them while it is pinned);
a host at that tag runs this section from a default-branch clone.

**2026-09-23 decision: brew-services semantics, no backup or reconcile.**

- **Chosen:** stateless, path-verified ownership with no backup, no
  rollback and no ownership file -- the same model Homebrew's own
  `brew services` uses. In **Homebrew/brew
  `Library/Homebrew/services/cli.rb` @ `8e3a5dc0a7`** (2026-09-07): `stop`
  boots a service out and then removes its service file (`stop`, roughly
  lines 229-247); `install_service_file` writes a temp file, removes the
  old service file and installs the new one (roughly lines 523-560), then
  `launchctl_load` calls `launchctl enable` followed by `launchctl
  bootstrap` (roughly lines 460-468); there is no backup, no rollback and
  no ownership file anywhere in that flow -- recovery is re-running the
  command. `launchd-agents.sh` now works the same way: "ours" means the
  label is one of this script's own AND, if it is currently loaded at all,
  the `path =` line `launchctl print` reports names this script's own
  destination plist, never a stored ownership record.
- **Rejected:** the transactional backup/reconcile design (round 3b
  through round 3f: a hard-linked backup plus a `reconcile_install`
  function, registered as both an explicit post-install step and the
  script's `EXIT` trap, that tried to converge whatever state a signal or
  a failure left behind). Every one of five successive review rounds found
  a NEW recovery defect in that machinery that the previous round's fix
  had not covered -- a partial copy overwriting the original, a reload
  never attempted at a bootout/reload boundary, a retry that could delete
  the only good backup, a tri-state `launchctl print` collapsed to a
  binary check, an unrelated service sharing a label getting recorded as
  owned, and a delayed teardown read as "nothing to do" -- which is
  itself the pattern that motivated retiring the whole approach rather
  than patching a sixth defect into it.
- **Would overturn this:** a real-Mac observation where re-running
  `install` (or `remove`) does not converge from a state an earlier,
  interrupted run left behind -- the one guarantee this design depends on,
  parallel to what `brew services` itself relies on -- or a new
  requirement to preserve a plist a person edited locally by hand (this
  design has no backup, so a local edit to a plist under
  `~/Library/LaunchAgents` is silently overwritten by the next `install`,
  exactly like `brew services` would overwrite it too).

Recovering a previous plist after a change is therefore no longer this
script's job: reproduce it from git history (`adoption/launchd/*.plist.
template`) plus whatever host value file (`adoption/hosts/<name>.json` or
`--set`) produced it, and render + install again.

**Untested boundary for real-Mac acceptance: asynchronous launchd teardown was
modelled, not observed natively.** Both `install`'s bootout gate and
`remove` assume a `launchctl bootout` that returns success can still leave
the old instance tearing down for a bounded time afterward -- a `launchctl
print` moments later can keep reporting it loaded during that window -- and
poll (`wait_until_unloaded`, a bounded, sleep-based loop) rather than
trusting one such read and proceeding immediately. This is source-supported
inference from `launchctl(1)`'s own documented behavior (a real Mac's `man
launchctl`; `bootout` and `bootstrap` are documented as asynchronous
relative to the daemon's own teardown/startup) and the shimmed/simulated
evidence in `tests/test_adoption_launchd.py` (a mock `launchctl` models a
delayed-loaded window with a bounded call counter, and real bash `SIGTERM`/
`SIGINT` injection exercises the deferred-signal path), never a native
observation of an actual delayed teardown on real launchd: no Mac, hosted
or otherwise, has produced a `launchctl bootout` whose corresponding
`launchctl print` stayed loaded for any measured, non-zero duration
afterward. A real Mac run should specifically try to reproduce that window
(e.g. a service with a slow `KeepAlive` shutdown path) rather than assume
the bounded poll alone is proof it behaves correctly there.

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
