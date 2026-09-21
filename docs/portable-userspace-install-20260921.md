# Clean userspace installation qualification — September 21, 2026 UTC

The selected token tools, native clients and two ECC skills installed in a fresh
official Ubuntu Base 24.04.5 amd64 filesystem. The unchanged existing token
fixture runner passed 41 native commands and 14 semantic checks. Both native
clients remained signed out. Repeated installation, overwrite protection and
rollback checks passed within the scope below.

This is **fresh Linux userspace on the existing WSL kernel**. It is not a booted
new PC, independent kernel, physical-machine qualification, native signed-in
inference test, provider-cost comparison or full-foundation deployment. The
source checkout was `3cabcdfd0c3b489867364d9582df8f356586d219`.

## Isolation and provenance

Docker and Podman were absent. The installed `bwrap` successfully created user,
mount, PID, IPC and UTS namespaces. An owned temporary directory held the new
root filesystem; no host home, authentication stores, project directory, Windows
mount, package cache or tool installation was mounted into it. `/source` came
from `git archive` of the stated commit. Only the host resolver configuration
was mounted read-only, and an owned output directory was mounted at `/results`.
Networking remained shared for upstream downloads. This is an installation
test boundary, not a new security-isolation product.

The child environment was cleared, preserving only the existing `HOME` value
and explicit PATH, locale and terminal settings. `HOME` was not redirected:
its same pathname referred to an initially empty directory inside the new root
filesystem. `CODEX_HOME` and provider credentials were not forwarded. Published
logs normalize that pathname to `/home/example`; upstream hashes remain exact.
Raw apt progress and the unchanged vendor installer retain original whitespace;
their narrowly scoped Git attributes preserve those bytes. Authored documents
and receipts use the normal whitespace checks.

The [official Ubuntu archive](https://cdimage.ubuntu.com/ubuntu-base/releases/24.04/release/ubuntu-base-24.04.5-base-amd64.tar.gz)
matched SHA256 `e77b6f10c2590cef872b33ee9f635a0e3fd1f57fb074c0e52b5c7f56147a0c86`.
Its SHA256SUMS signature verified against the installed Ubuntu archive keyring,
using fingerprint `843938DF228D22F7B3742BC0D94AA3F0EFE21092`.
The [Node 24.21.0 LTS archive](https://nodejs.org/en/download/archive/v24.21.0)
matched the publisher's SHA256 list:
`fd8e59d5a511510f6a298afb548f18c7d2b1be404d8b4a27d94fbe49f56cb2d6`.
Node's detached signature was not separately verified.

## What passed

| Component | Exact selected source | Observed result |
| --- | --- | --- |
| RTK | 0.49.0, upstream Linux musl archive/checksum | Real Git fixture; both commit subjects preserved; raw proxy output exact; expected error retained; counter increased by three. |
| QMD | `@tobilu/qmd@2.8.3` via npm | BM25 collection/search/get/update reproduced exact document content; no model files downloaded. |
| Repomix | `repomix@1.18.0` via npm | Explicit selected source content retained; compressed structural output checked separately. |
| TOON | `@toon-format/cli@4.1.1` via npm | JSON → TOON → JSON preserved exact values. No general savings claim. |
| Codex | `@openai/codex@0.155.1` via npm | Exact CLI version, repeat installation, one top-level package entry, expected signed-out status; uninstall and repeated uninstall succeeded. |
| Claude Code | Official native installer, target `2.1.278` | Exact version, repeated native installation kept identical binary hash, expected signed-out status; native binary rollback succeeded. |
| ECC skills | `affaan-m/ECC@2b6e839771e53096d8451a213d40dc64ec8acac0` | Both selected skill files matched prior source hashes; repeated install refused existing destinations without changes; Claude symlinks resolved; rollback removed both skills and links. |

The token checks reused [the existing runner](../scripts/native_token_ci.py)
unchanged, SHA256 `f1bb054a244160a4c8fc1674ff658aa67d6a3f9dc9e79b86b30e32794c5d0983`.
It invokes upstream installers and CLIs; its fixtures and assertions are local
integration checks, **not upstream projects' full test suites**. Its retained
[successful receipt](../evidence/artifacts/portable-userspace-install-20260921/token-clean-install-unprivileged/receipt.json)
includes all 41 commands and outputs, 14 assertions and scratch-directory removal.
Top-level npm versions are pinned; transitive dependencies resolved at install
time and are not a fully locked dependency graph.

Claude's installed binary matched publisher SHA256
`5c4735937844e84f8a93306e841a5b0e12252909b07870f789b190468da147ab`.
The retained manifest signature verified using the fingerprint documented by
[Anthropic](https://code.claude.com/docs/en/setup#binary-integrity-and-code-signing),
`31DDDE24DDFAB679F42D7BD2BAA929FF1A7ECACE`. The public signing key was processed
with an owned temporary GPG directory, without changing the user's keyring.

The ECC installer was the unmodified official OpenAI skill-installer from
[`openai/skills@49f948faa9258a0c61caceaf225e179651397431`](https://github.com/openai/skills/tree/49f948faa9258a0c61caceaf225e179651397431/skills/.system/skill-installer/scripts).
The existing-destination refusal is overwrite protection, not a successful
idempotent installer run. Skill linkage is filesystem evidence; account-free
checks do not demonstrate model invocation or native initialization discovery.

## Native commands and retained failures

Commands executed inside the isolated root filesystem, using root-mapped UID 0
only for OS/bootstrap installation and ordinary UID 1000 for the passing token
checks, repeated client installation, skills and rollback:

```sh
apt-get -o APT::Sandbox::User=root update
DEBIAN_FRONTEND=noninteractive apt-get -o APT::Sandbox::User=root install -y \
  --no-install-recommends ca-certificates curl git python3 xz-utils libatomic1
sha256sum --check --ignore-missing SHASUMS256.txt
tar --no-same-owner -xJf node-v24.21.0-linux-x64.tar.xz \
  --strip-components=1 -C /usr/local
python3 /source/scripts/native_token_ci.py --install \
  --output /results/token-clean-install-unprivileged
npm install --global --prefix /practice/native \
  --registry=https://registry.npmjs.org --no-audit --no-fund @openai/codex@0.155.1
codex --version
codex login status
bash claude-install.sh 2.1.278
claude install 2.1.278
claude --version
claude auth status
python3 skill-installer/install-skill-from-github.py \
  --repo affaan-m/ECC --ref 2b6e839771e53096d8451a213d40dc64ec8acac0 \
  --path skills/search-first skills/iterative-retrieval \
  --dest /home/example/.agents/skills
npm uninstall --global --prefix /practice/native --no-audit --no-fund @openai/codex
```

The exact namespace invocation shape and command outcomes are in the
[machine-readable receipt](../evidence/receipts/portable-userspace-install-20260921.json).
The two native auth-status commands returned exit 1 as expected because no
credentials existed. Initial combined install/status invocations consequently
returned 1; later checks explicitly asserted that expected signed-out exit.

All attempts remain recorded:

1. Initial apt bootstrap failed because a single-UID user namespace cannot
   switch to `_apt`. The per-command `APT::Sandbox::User=root` option succeeded
   inside the disposable namespace; no host apt configuration was changed.
2. Initial Node extraction failed while trying to restore upstream archive UID
   ownership. `tar --no-same-owner` succeeded in this root-mapped namespace.
3. The first unchanged token-runner attempt failed its RTK extraction for the
   same ownership reason. Its other components completed. Rather than patching
   the runner, it was rerun with ordinary UID 1000 and all checks passed.

No provider model request, account login, paid service, host update, persistent
daemon or reboot was performed. The native installer noted its bin directory
was initially outside PATH; later invocations used the explicit isolated PATH.

## Cleanup and remaining boundary

The token runner removed its owned installation and fixture directories after
each attempt. Codex's upstream npm uninstall was run twice. Claude's documented
native removal paths and the two newly installed skill directories/symlinks
were removed only inside the disposable root. Absence checks passed; both
credential paths remained absent. The owned root filesystem, downloads and
temporary GPG directory were then removed after the public evidence was retained.

A future PC still needs its own supported OS/dependencies, native sign-in,
terminal interaction, selected scoped integrations and representative task
checks. This result closes a clean-userspace installation gap for the named
subset; it does not promote every catalog entry or the entire ecosystem to
portable E2E acceptance.
