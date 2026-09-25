# Decision: retire the Vela and VelaNext WSL distros on the workstation (2026-09-25)

**Decided by:** the user, on the Windows PC that hosts `nativestack-5975wx-20260925`. A
Claude Code session there carried out the cleanup on 2026-09-25.

**Scope:** the Windows Subsystem for Linux distros on that PC. The decision covers no other host
or repository record.

## Decision

Vela and VelaNext were unregistered on 2026-09-25. Two distros remain on that PC:

- NativeStack, the Claude Code and Codex ecosystem host, recorded as `nativestack-5975wx-20260925`.
- Polaris, kept for its own services outside this repository.

The user chose to drop VelaNext's SSH path from the Mac along with it.

## What was kept

Before unregistering, the session saved the salvage to a private archive outside every
repository, with a SHA-256 manifest. Every archive file was verified against it before the
distros were removed. The archive holds:

- git bundles of branches and worktrees that were not on a remote;
- patches of uncommitted work;
- the private originals behind VelaNext's 2026-09-20 receipts.

Credential stores were not read or copied, and the user was asked to revoke the provider keys
that lived there. Model weights, transcripts and stale work trees were dropped as superseded.

## Consequences for repository records

- **Past receipts stay valid as history.** Receipts and decisions recorded on VelaNext before
  2026-09-25 are dated evidence and stay unchanged; for example, catalog evidence ids such as
  `velanext-native-quality-tools-20260920`. They are not a current host's status.
- **New runs need another host.** VelaNext is no longer available for new runs. The 2026-09-25
  memory-stack record (`catalogs/foundation/memory-stack-20260925.json`) puts two things on
  VelaNext:
  - its trial isolation;
  - the confirmatory rerun, which amendment A15 fixes as "one platform per comparison".

  Those runs now need another host, and a new preregistration amendment naming it, before any
  run. No confirmatory rerun and no C4 result was recorded in this repository before the
  retirement.
- **This document is the repository evidence for the retirement.** The archive and the cleanup
  log are private and are not evidence of record.
