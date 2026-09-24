# Decision: broker paper-credential file handling (2026-09-22)

**Decided by:** unit `pr4-gate-credentials`, catalog integration branch `claude/grand-catalog-20260922`; the coordinator mirrors a pointer into agent-lab.

**Scope:** `blueprints/us-equities/adaptive-paper/runner.py`'s `credentials(path)` only. `runner.py`'s caller
does not change; this decision only tightens the precondition on the env file that `--env-file` names before
it is opened. No broker call, no live credentials file, and no new secret store are introduced.

`market_research.py` (same directory) has its own, differently implemented `credentials(path)` that also
reads an Alpaca env file named by its own `--env-file` flag. **Closed 2026-09-24, hardened in a same-day fix
round** (see `catalogs/us-equities/gates-20260922.json`'s `credential-handling` gate note for the exact,
qualified guarantee): both loaders now call a shared
`blueprints/us-equities/adaptive-paper/credential_guard.open_verified()` for the ownership (current uid via
`os.getuid()`), mode (exactly `0600`), hard-link-count (exactly 1), immediate-parent-directory
ownership/writability, and outside-any-Git-worktree rules. These are bound to a `dir_fd`-chained traversal
from `/` (`O_DIRECTORY|O_NOFOLLOW` per ancestor, `O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_NOCTTY` for the file) so a
symlink substituted at any position -- an ancestor directory, not only the final file -- fails closed with
`ELOOP`/`ENOTDIR`, rather than the earlier fstat-vs-pre-open-lstat comparison (which only re-checked the
final component and did not bind the directory chain itself). `market_research.py` keeps its original
`O_NOFOLLOW` symlink-refusal behavior (`follow_symlinks=False`, now also applied per-ancestor-component, not
only the final file); `runner.py` keeps its original symlink-resolving behavior (`follow_symlinks=True`) so
this runner's asserted `credential_file_permissions` error-string substring is unchanged. Every rejection
raises one fixed, path-free message (`credential_guard.GUARD_DENIED`) -- no path, basename, or upstream
`OSError` text is ever included. Covered by `tests.test_adaptive_paper_runner.CredentialFilePermissions`
(existing, still passing, plus new symlink, hard-link, and FIFO-does-not-hang cases), the new
`tests.test_adaptive_paper_runner.SharedCredentialGuardParity`, the new
`tests.test_adaptive_market_research.MarketResearchCredentialFilePermissions` (wrong mode, wrong owner,
symlink, hard link, inside a Git worktree, missing file, a FIFO that must not hang, and a valid file), and
the new `tests/test_credential_guard_race.py` (deterministic hook-injected mid-traversal swaps, a
naive-vs-guarded comparison demonstrating the ancestor-directory race the fix round closed, deadline-bounded
no-hang checks, and a mutation-kill report).

## Decision

Keep the existing native mechanism -- an explicit, operator-selected `--env-file` (private, plaintext
`APCA_API_KEY_ID=...` / `APCA_API_SECRET_KEY=...` lines) -- but enforce fail-closed preconditions on that
file in code before any line is read:

1. **Mode exactly `0600`.** Group- or other-readable (or any other bit set) is rejected.
2. **Owned by the current uid.** `os.getuid()` -- the real user id this process runs as, not any notion of
   an "effective user" -- must match the file's owner; a file inherited from another user or a shared mount
   is rejected.
3. **Exactly one hard link.** A second name for the same inode (e.g. hard-linked from inside a worktree
   while the checked name lives outside one) is rejected, since the guarantee below only inspects the name
   that was opened.
4. **Immediate parent directory owned by you and not group- or other-writable.**
5. **Outside any Git worktree it is possible to detect from the file's own location.** `credentials()` walks
   the opened directory chain for a `.git` entry (directory in an ordinary clone, file in a linked worktree)
   and rejects the file if one is found at any ancestor. This is a real, useful check, not a proof: a
   worktree configured purely through `GIT_DIR`/`GIT_WORK_TREE` environment variables or `core.worktree`,
   with no `.git` entry anywhere in the file's own ancestor chain, is undetectable by a file-local check and
   is **not** caught. "Outside any Git worktree" here means "outside every worktree whose `.git` entry is an
   ancestor of this path" -- it is not a claim that the file can never be committed, diffed, or swept up by
   every possible repository-wide scan.

Every rule above is bound to the exact `dir_fd`-chained traversal that produces the descriptor read from --
see `blueprints/us-equities/adaptive-paper/credential_guard.py`'s module docstring for precisely what that
does and does not guarantee against a filesystem change made after the check starts.

Each violation raises the same fixed, path-free message via `credential_guard.GUARD_DENIED`, wrapped by each
caller in its own exception type: `runner.credentials()` raises `SafetyError("credential_file_permissions:
...")`; `market_research.credentials()` raises `ResearchError("credential_file_permissions: ...")` (a
`ResearchError`, not a `SafetyError` -- the two loaders share the guard's rules and message, not an
exception type). No raised error ever includes the file's path, basename, content, or an upstream `OSError`'s
text. Conventional placement is a private path such as `~/.config/<tool>/paper.env`, outside every checkout,
loaded only by the existing `--env-file` mechanism.

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

`local_integration`: `tests/test_adaptive_paper_runner.py`'s `CredentialFilePermissions` class and
`tests/test_adaptive_market_research.py`'s `MarketResearchCredentialFilePermissions` class exercise the
mode/owner/hard-link/parent-directory/worktree checks with temporary files and `os.chmod`/mocked
`os.getuid`, and confirm the raised error never contains the file's key/secret values, a path, or a
basename. `tests/test_credential_guard_race.py` deterministically injects a mid-traversal filesystem swap
(via a monkeypatched hook, not real concurrency) for a symlinked ancestor directory, a symlinked or FIFO
final component, and a metadata change between open and fstat; bounds every "does not hang" assertion with a
`signal.alarm` deadline; and runs a small mutation suite that disables one guard protection at a time and
asserts a specific test now fails to reject the case that protection existed for (a mutation-kill report).
No broker call is made and no live credentials file is read or referenced.
