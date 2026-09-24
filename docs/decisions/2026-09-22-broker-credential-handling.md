# Decision: broker paper-credential file handling (2026-09-22)

**Decided by:** unit `pr4-gate-credentials`, catalog integration branch `claude/grand-catalog-20260922`; the coordinator mirrors a pointer into agent-lab.

**Scope:** `blueprints/us-equities/adaptive-paper/runner.py`'s `credentials(path)` only. `runner.py`'s caller
does not change; this decision only tightens the precondition on the env file that `--env-file` names before
it is opened. No broker call, no live credentials file, and no new secret store are introduced.

`market_research.py` (same directory) has its own, differently implemented `credentials(path)` that also
reads an Alpaca env file named by its own `--env-file` flag. **Closed 2026-09-24** (see
`catalogs/us-equities/gates-20260922.json`'s `credential-handling` gate): both loaders now call a shared
`blueprints/us-equities/adaptive-paper/credential_guard.open_verified()` for the ownership (current uid),
mode (exactly `0600`), and outside-any-Git-worktree rules, with a TOCTOU-safe fstat-vs-lstat re-check on the
opened descriptor (the pattern `tools/credentials/alpaca_rate_limit_probe.py:read_env_file` already used).
`market_research.py` keeps its size cap and its original `O_NOFOLLOW` symlink-refusal behavior
(`follow_symlinks=False`); `runner.py` keeps its original symlink-resolving behavior
(`follow_symlinks=True`) so this runner's asserted error-string substrings are unchanged. Covered by
`tests.test_adaptive_paper_runner.CredentialFilePermissions` (existing, still passing, plus new
`test_symlink_to_a_valid_target_is_resolved_and_accepted` and `test_fifo_is_rejected_and_does_not_hang`),
the new `tests.test_adaptive_paper_runner.SharedCredentialGuardParity`, and the new
`tests.test_adaptive_market_research.MarketResearchCredentialFilePermissions` (wrong mode, wrong owner,
symlink, inside a Git worktree, missing file, a FIFO that must not hang, and a valid file).

## Decision

Keep the existing native mechanism -- an explicit, operator-selected `--env-file` (private, plaintext
`APCA_API_KEY_ID=...` / `APCA_API_SECRET_KEY=...` lines) -- but enforce fail-closed preconditions on that
file in code before any line is read:

1. **Mode exactly `0600`.** Group- or other-readable (or any other bit set) is rejected.
2. **Owned by the current uid.** A file inherited from another user or a shared mount is rejected.
3. **Outside any Git worktree.** `credentials()` walks the resolved file's parents for a `.git` entry
   (directory in an ordinary clone, file in a linked worktree) and rejects the file if one is found, so a
   credential file can never be committed, diffed, or swept up by a repository-wide scan by construction.

Each violation raises `SafetyError("credential_file_permissions: <one-line remediation>")` -- a single
matchable reason-code prefix with a short instruction (`chmod 600 ...`, `chown` to the current account, or
move the file outside the repository) -- before any content is read. The file's contents are never included
in the raised error, logged, or otherwise echoed. Conventional placement is a private path such as
`~/.config/<tool>/paper.env`, outside every checkout, loaded only by the existing `--env-file` mechanism.

## Alternatives considered

- **OpenBao (or another secrets service).** Conditional entry in the catalog; a dev-mode server is
  unsuitable for a credential this sensitive, and running it in a hardened mode is only justified once
  there is unattended, multi-service hosting actually consuming the secret. Rejected for this single
  operator-invoked CLI.
- **OS keychain (e.g. macOS Keychain).** Platform-specific; this host's runtime profile is Linux/WSL.
  Deferred to a macOS-specific profile if one is adopted; not a general replacement here.
- **Environment variables set directly in the invoking shell.** Rejected: shell-exported credentials leak
  into `/proc/<pid>/environ`, process listings, and every child process's environment, which is a strictly
  larger blast radius than a single `0600`, non-worktree file opened only by this process.

## Evidence that would overturn this decision

- Unattended, multi-host hosting of the paper (or live) runner, where a human is no longer present to
  select `--env-file` interactively at each invocation.
- A second consumer of the same broker secret (e.g. a separate service or scheduler) that needs shared,
  access-controlled retrieval rather than a single operator-local file.
- A `gitleaks` (or equivalent) finding that an env path matching this convention was ever tracked, staged,
  or present in history for any repository.

## Evidence class

`local_integration`: `tests/test_adaptive_paper_runner.py`'s `CredentialFilePermissions` class exercises the
mode/owner/worktree checks with temporary files and `os.chmod`/mocked `os.getuid`, and confirms the raised
error never contains the file's key/secret values. No broker call is made and no live credentials file is
read or referenced.
