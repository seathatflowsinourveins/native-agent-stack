# Decision: a signed live go, and rung readiness that needs holding evidence (2026-09-25)

**Chosen by:** the coordinator of the 2026-09-25 live-gates workflow, as its checker-hardening stage. The
2026-09-25 readiness review offered two controls for live-go authorship: a detached signature checked by
`ssh-keygen -Y verify`, or a ruleset that requires a distinct reviewer. The stage brief selected the
signature. This is a coordinator choice, subject to independent review. The user owns the signing key, the
allowed_signers entry, `docs/decisions/live-go.md` and every go.

**Scope:** `scripts/trading_gates.py`, `tests/test_trading_gates.py`, the `authorship` block and the
`live-go` note in `catalogs/us-equities/gates-20260922.json`, and the setup section of
`catalogs/us-equities/README.md`. No other gate's status, condition or evidence rule changes, and no gate is
flipped.

## Evidence

- **Readiness read only recorded statuses.** At `origin/main` 0074a0c3, `check()` computed the pending gates
  as the required gates whose status was not `established` (`scripts/trading_gates.py:293`). An established
  gate whose receipt was missing or failing produced an error, but its rung still counted as ready. The
  readiness review's simulation V1 showed `status: failed` alongside `rung_ready.live: true`. The new test
  `test_established_gate_whose_condition_fails_blocks_its_rung_and_every_later_rung` fails against the
  0074a0c3 checker and passes against this one.
- **live-go was protected only by its note.** A null `flip_condition` was judged as the presence of a
  non-empty file (`scripts/trading_gates.py:183-186` at 0074a0c3). A placeholder `live-go.md`, a status
  change and any evidence class other than `none` therefore made live-go count. The main ruleset requires 0
  approving reviews (`.github/main-ruleset.json`, `required_approving_review_count: 0`), and agent sessions
  push under the user's GitHub identity. Review alone therefore cannot separate an agent's commit from the
  user's.
- **`ssh-keygen -Y verify` is available and fails closed.** It was measured with a throwaway ed25519 key
  under OpenSSH_9.6p1 on the WSL workstation. A good signature exits 0 and prints
  `Good "<namespace>" signature for <principal> with ED25519 key SHA256:...`. Each of the following exits
  255:
  - an edited document;
  - a principal that the allowed_signers file does not list;
  - another signing namespace, including `file`;
  - a key restricted to another namespace;
  - a key past its `valid-before` date;
  - a missing allowed_signers file or signature.

  `ssh-keygen -Y sign` stops at an overwrite prompt when the `.sig` already exists, so the setup removes an
  old signature first. The required CI jobs run the full unit suite on ubuntu-24.04 (`validate`) and on
  macos-15 (`validate-macos`). The new signature tests skip only on a host without `ssh-keygen`.

## Decision

1. **Evidence class `user_decision`.** It is valid only for a gate owned by `user-decision` whose
   `flip_condition` is null; the checker refuses it anywhere else. Every other evidence class keeps its
   rules.
2. **Readiness needs holding evidence.** A required gate counts toward `rung_ready` only while it is recorded
   `established` and its condition holds now. An established gate whose receipt is missing or failing, or
   whose signature does not verify, is listed in `blocking` and keeps its rung and every later rung not
   ready. The error it already produced is unchanged.
3. **live-go authorship.** The gates document's top-level `authorship` block names, for `live-go`:
   - the method `ssh-keygen -Y verify`;
   - `signature_path` `docs/decisions/live-go.md.sig`;
   - `allowed_signers_path` `docs/decisions/live-go.allowed_signers`;
   - the principal `live-go-signer`;
   - the namespace `live-go@native-agent-stack`.

   live-go holds only when its receipt is non-empty and that verification accepts the receipt's exact bytes.
   Anything else fails closed:
   - an absent or empty document, signature or allowed_signers file;
   - a path that resolves outside the tree;
   - a host without `ssh-keygen`;
   - a timeout or a non-zero exit.

   The checker refuses a catalog whose `live-go` gate names no control, so deleting the block alone cannot
   make live-go presence-only. live-go also never holds for a caller that passes no control. Recorded
   established, live-go must carry `user_decision`. Only a gate owned by `user-decision` with a null flip
   condition may have a control. The checker runs `ssh-keygen` with tree-relative paths from the tree root,
   and it never writes a file.

No key, signature, allowed_signers entry or `live-go.md` was created. The tests generate throwaway ed25519
keys in temporary directories outside the tree under test and delete them afterwards. The user's one-time
setup is in `catalogs/us-equities/README.md`.

## Sources

- **OpenSSH `ssh-keygen`**, installed rather than reimplemented. Source: openssh/openssh-portable, tag
  `V_9_6_P1` (commit b24f772e), `ssh-keygen.1`:
  - `-Y verify` (lines 765-790) reads the message on standard input, with `-n` namespace, `-s` signature, `-I`
    signer identity and `-f` allowed signers. "Successful verification by an authorized signer is signalled
    by returning a zero exit status", so the checker counts only exit 0 as verified.
  - ALLOWED SIGNERS (from line 1225) gives the file format and the `namespaces=` and `valid-before=` options
    used in the setup.
  - Lines 758-764 advise custom namespaces of the form NAMESPACE@YOUR.DOMAIN, hence
    `live-go@native-agent-stack`.
- **git's SSH signature verification**, the reference for the invocation. Source: git/git, tag `v2.43.0`,
  `gpg-interface.c`, `verify_ssh_signed_buffer` (lines 447-580). It refuses when no allowed signers file is
  configured (469-472), and runs `ssh-keygen -Y verify -n <namespace> -f <allowed signers> -I <principal>
  -s <signature>` with the payload on standard input (557-575). This checker differs in two ways:
  - it pins the principal in the catalog instead of finding it with `-Y find-principals`;
  - it passes no `-Overify-time`, so an allowed_signers `valid-before` expiry applies at check time.
- **The readiness predicate and the `user_decision` class** change this repository's own checker contract,
  the gates document's scope. No external implementation applies to those two predicates.

## Alternatives considered

- **A ruleset that requires a distinct reviewer on `live-go.md` and the gates file.** This was the readiness
  review's other option. It is not the chosen control: the repository has one maintainer, agents act under
  that identity, and "distinct" needs a second account. Changing the ruleset is the user's decision, so it
  stays an optional complement.
- **Signed commits (`git verify-commit`, GitHub's "Verified" mark).** Main takes squash merges, which GitHub
  commits itself, so a signature on the user's own commit does not reach main. A detached signature over the
  file's bytes survives any merge method.
- **A GPG detached signature.** It would need a keyring on every CI runner and host. `ssh-keygen` is already
  on the runners and hosts, and its allowed_signers file is plain text in the tree.
- **Sigstore or gitsign keyless signing.** Signing needs network access and an OIDC identity, and
  verification needs the Sigstore trust root and another tool (cosign or gitsign). The checker is offline
  standard-library code plus one system tool.
- **minisign or signify.** Each adds a tool and a key format that this ecosystem does not already use. SSH
  keys and `ssh-keygen` are already in use on its hosts. Whether the CI runner images ship either tool was not
  checked.
- **Pinning the signer outside the tree, to the repository owner's GitHub SSH signing keys.** The Codex
  review of PR #295 asked for this (P1). GitHub publishes each account's signing keys at
  `GET /users/{owner}/ssh_signing_keys`; on 2026-09-25 the owner had none registered (HTTP 200, 0 keys).
  Changing that list needs the `admin:ssh_signing_key` token scope or a web re-authentication. The gh token
  on the WSL workstation carries only `gist`, `read:org`, `repo` and `workflow` (measured with
  `gh auth status`). Requiring the verifying key to be on that list would put the trust root outside what
  agent sessions on that host can change.

  It is not in this change, because it needs two decisions that are the user's:
  - registering a dedicated signing key on the account;
  - a network dependency in the checker, or in a new required CI step, which then fails closed whenever
    GitHub cannot be reached.

  It also leaves the enforcing code in the tree. Anyone who can merge can still edit that code, because main
  requires 0 approvals. A forgery would move from a data edit to a code edit, which review sees more
  readily, but it would not become impossible.

## What would overturn it

- The user deciding to bind the signer to the owner's GitHub signing keys (the alternative above). It would
  then be added as a fail-closed check next to `ssh-keygen -Y verify`.
- A demonstrated path for an agent session to make live-go verify without the user's key, beyond replacing
  the allowed_signers file (see limits). The response would then be the account-bound pin above, or a
  required-reviewer ruleset.
- A second maintainer or reviewer account. The ruleset control then becomes possible; compare the two on the
  same attempted agent flip.
- An OpenSSH release that changes what `ssh-keygen -Y verify` accepts or how it exits. The signature tests
  run the host's own `ssh-keygen` wherever one is installed and skip only where none is, so a unit-suite run
  on a host with such a release would show the change.

## Limits

- The allowed_signers file lives in the tree, so anyone with write access can replace it. A replacement shows
  in that file's diff and history, but the checker does not prevent it. A key that needs a physical touch
  keeps agent sessions from signing with the registered key. It does not stop a registered key from being
  replaced.
- A software key that agent sessions can read, or one loaded into an agent they can reach, defeats the
  control. The setup therefore recommends a hardware-backed key or a passphrase-protected key that no such
  agent holds.
- The checker runs the first `ssh-keygen` on `PATH`, so a local run trusts that host's environment. The
  enforcing run is the required CI jobs' unit suite, whose repository test fails on any error from an
  established live-go that does not verify, on the runner image's own `ssh-keygen`.
- The checker verifies who signed `live-go.md`, not what it says. This change adds no format lint for its
  content.
- `docs/grand-catalog-handbook.md` still says no checker can evaluate live-go. It is a shared document and is
  left to its owner.
