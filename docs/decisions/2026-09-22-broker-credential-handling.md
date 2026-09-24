# Decision: broker paper-credential file handling (2026-09-22)

**Decided by:** unit `pr4-gate-credentials`, catalog integration branch `claude/grand-catalog-20260922`; the coordinator mirrors a pointer into agent-lab.

**Scope:** `blueprints/us-equities/adaptive-paper/runner.py`'s `credentials(path)` only. `runner.py`'s caller
does not change; this decision only tightens the precondition on the env file that `--env-file` names before
it is opened. No broker call, no live credentials file, and no new secret store are introduced.

`market_research.py` (same directory) has its own, differently implemented `credentials(path)` that also
reads an Alpaca env file named by its own `--env-file` flag. **Closed 2026-09-24, hardened across two
same-day fix rounds** after independent Codex security review and an independent Claude real-mutation/attack
run (see `catalogs/us-equities/gates-20260922.json`'s `credential-handling` gate note for the current,
qualified guarantee): both loaders now call a shared
`blueprints/us-equities/adaptive-paper/credential_guard.open_verified()` for the ownership, mode (exactly
`0600` for the file), hard-link-count (exactly 1 for the file), whole-ancestor-chain
ownership/writability (root or `os.getuid()`; group/other-writable only if sticky, the OpenSSH
`safe_path`/`secure_filename` model), and outside-any-Git-worktree rules. These are bound to a
`dir_fd`-chained traversal from `/` (`O_DIRECTORY|O_NOFOLLOW` per ancestor,
`O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_NOCTTY` for the file) so a symlink substituted at any position -- an
ancestor directory, not only the final file -- fails closed with `ELOOP`/`ENOTDIR`. Renaming an
already-checked, victim-owned directory underneath an attacker-writable, non-sticky ancestor (the round-2
Codex finding) no longer bypasses anything, because that ancestor itself is refused the moment it is opened,
independent of what gets renamed into it afterward or when. `market_research.py` keeps its original
`O_NOFOLLOW` symlink-refusal behavior (`follow_symlinks=False`, applied per-ancestor-component, not only the
final file, and a lexical `..` component is refused outright rather than silently collapsed -- collapsing it
could skip inspecting an intermediate symlink); `runner.py` keeps its original symlink-resolving behavior
(`follow_symlinks=True`) so this runner's asserted `credential_file_permissions` error-string prefix is
unchanged. Every rejection raises one of a small, fixed set of path-free `credential_file_permissions:<code>`
reason codes (`credential_guard.REASON_*`, e.g. `:owner`, `:mode`, `:hardlink`, `:worktree`, `:ancestor`,
`:parent_owner`, `:parent_mode`, `:symlink`, `:not_regular`, `:missing`, `:encoding`, `:size`) -- never a
path, a basename, or upstream `OSError`/`RuntimeError` text; a circular-symlink `RuntimeError` (which
`Path.resolve(strict=True)` raises, not `OSError`, on the native Python 3.12 runtime) and an embedded-NUL
`ValueError` are both caught and normalized the same way. Every such exception is also built and raised from
code that is no longer inside the `except` block that caught the original failure, specifically so Python
never attaches that original (potentially path-bearing) exception as `__context__`; `from None` alone does
not achieve this, since the interpreter re-populates `__context__` at the `raise` statement itself if one is
still executing inside a handler. The verified descriptor is closed on every failure path, including an
`fdopen()` failure after every other check has already passed. Covered by
`tests.test_adaptive_paper_runner.CredentialFilePermissions` (existing, still passing, plus symlink,
hard-link, FIFO-does-not-hang, and non-ASCII cases, each FIFO case now under a `signal.alarm` deadline), the
existing `tests.test_adaptive_paper_runner.SharedCredentialGuardParity`, the existing
`tests.test_adaptive_market_research.MarketResearchCredentialFilePermissions` (wrong mode, wrong owner,
symlink, hard link, inside a Git worktree, missing file, a deadline-bounded FIFO, and a valid file), and
`tests/test_adaptive_paper_credential_race.py` -- note the real filename; an earlier round of this document
named a nonexistent `tests/test_credential_guard_race.py`. That file's `HookInjectedRaces`,
`AncestorRenameResistance`, `NoPathLeakInErrors`, `DotDotIsRejected`, `FdOpenFailureCleanup`,
`FdLeakOnRefusal`, `RootMarkerIsChecked`, `ForeignFileOwnerAloneIsRejected`, `FstatNotPathnameStat`, and
`BoundedReadIsActuallyBounded` classes exercise the round-2 findings specifically (a hook-injected mid-walk
worktree marker, simulated foreign ownership via per-fd `fstat` faking rather than a process-wide
`os.getuid()` patch, error-content assertions that also check `__context__`/`__cause__` are `None`, a real
`os.listdir("/proc/<pid>/fd")` fd-count check around both success and every refusal path, and a
call-contract assertion on the exact `read()` size argument each loader uses -- not only the outcome, since a
static oversized fixture rejects identically whether the read is bounded or not). Its `RealMutationKills`
class replaces an earlier `MUTATION_KILLS` meta-test that only patched in-process Python objects and asserted
a hardcoded string-to-test-name mapping without ever running those tests -- flagged by the round-2 Codex
review as not establishing what it claimed to. `RealMutationKills` instead copies the actual source tree to a
private temporary directory (via `tests/_credential_mutation_driver.py`), applies one real, exact-count
textual mutation to a real `.py` file in that copy, and runs the actually-named test(s) against the mutated
copy in a subprocess; a mutation counts as "killed" only if that subprocess genuinely exits non-zero. All
twelve mutations currently declared there are killed this way (see that test's printed report for the
current list); "does not hang" is asserted the same way -- the `O_NONBLOCK`-removal mutation is confirmed to
make the FIFO test's own `signal.alarm` deadline fire and fail fast, not to hang the mutation run itself.

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
4. **Every ancestor directory from `/` down through the immediate parent -- not only the immediate
   parent -- owned by root or by you, and group-/other-writable only if it also carries the sticky bit.**
   This is the OpenSSH `safe_path`/`secure_filename` model. It is what makes a private, caller-owned
   directory under `/tmp` (sticky, world-writable) pass while an ordinary attacker-writable shared
   directory is refused outright, *regardless of what it contains or what gets renamed into it
   afterward* -- closing a round-2 finding where only the immediate parent's ownership/mode were checked,
   letting an attacker who can write to an ancestor two or more levels up rename an already-checked,
   victim-owned directory into a location a `.git` ancestor would otherwise catch.
5. **Outside any Git worktree it is possible to detect from the file's own location.** `credentials()` walks
   the opened directory chain -- including `/` itself, not starting only at the first named component -- for
   a `.git` entry (directory in an ordinary clone, file in a linked worktree) and rejects the file if one is
   found at any ancestor, checked at the moment each ancestor's own descriptor is opened (not from a
   pathname list computed once before any traversal happens, which a later rename could evade). This is a
   real, useful check, not a proof: a worktree configured purely through `GIT_DIR`/`GIT_WORK_TREE`
   environment variables or `core.worktree`, with no `.git` entry anywhere in the file's own ancestor chain,
   is undetectable by a file-local check and is **not** caught -- markerless worktrees of that shape remain
   fully out of scope. Likewise, a bind mount that makes a repository subdirectory appear at a path with no
   `.git` ancestor in its own mount namespace is invisible to this check; that requires mount authority (or
   an existing mount) to set up, and metadata checks do not categorically exclude virtual filesystems either.
   "Outside any Git worktree" here means "outside every worktree whose `.git` entry is an ancestor of this
   path, in this process's own mount namespace" -- it is not a claim that the file can never be committed,
   diffed, or swept up by every possible repository-wide scan.
6. **For `follow_symlinks=False` (`market_research.credentials()`), no `..` path component, ever.**
   Lexically collapsing `..` (the way `os.path.normpath` would) can select a different file through an
   intermediate symlinked component without ever refusing that symlink -- contradicting "a symlinked
   component is always refused". A `..` component is refused outright instead of normalized away.

Every rule above is bound to the exact `dir_fd`-chained traversal that produces the descriptor read from --
see `blueprints/us-equities/adaptive-paper/credential_guard.py`'s module docstring for precisely what that
does and does not guarantee against a filesystem change made after the check starts. In particular, a
compliant *replacement* file an equally-privileged attacker swaps in at the exact instant of the real
`open()` syscall is accepted by design (there is no TOCTOU there -- the fd read is the exact fd whose
metadata was just checked); this is the same acceptance `runner.credentials()`'s symlink-following mode
(`follow_symlinks=True`) already documents for a symlink whose target changes between the initial resolve and
the traversal.

Each violation raises one of the fixed, path-free `credential_file_permissions:<code>` reason codes listed
above, wrapped by each caller in its own exception type: `runner.credentials()` raises
`SafetyError("credential_file_permissions:<code>")`; `market_research.credentials()` raises
`ResearchError("credential_file_permissions:<code>")` (a `ResearchError`, not a `SafetyError` -- the two
loaders share the guard's rules and reason codes, not an exception type). No raised error ever includes the
file's path, basename, content, or an upstream `OSError`/`RuntimeError`'s text, and none of it is reachable
through `__context__` or `__cause__` either. Conventional placement is a private path such as
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

`local_integration`: `tests/test_adaptive_paper_runner.py`'s `CredentialFilePermissions` class and
`tests/test_adaptive_market_research.py`'s `MarketResearchCredentialFilePermissions` class exercise the
mode/owner/hard-link/ancestor-chain/worktree checks with temporary files and `os.chmod`/mocked `os.getuid`,
and confirm the raised error never contains the file's key/secret values, a path, or a basename; both
FIFO-does-not-hang tests run under a `signal.alarm` deadline. `tests/test_adaptive_paper_credential_race.py`
(the real filename -- see above) deterministically injects a mid-traversal filesystem swap (via a
monkeypatched `credential_guard._hook`, not real concurrency) for a symlinked ancestor directory, a symlinked
or FIFO final component, a `.git` marker added just before an ancestor is opened, and a metadata change
between open and fstat; simulates a foreign file/ancestor owner and a lying pathname `stat()` via per-fd
`fstat`/`os.open` faking (never a process-wide `os.getuid()` patch, which would also fail the parent-owner
check and mask what is actually being tested); asserts `__context__`/`__cause__` are `None` alongside every
path-free-message check; counts open file descriptors (`/proc/<pid>/fd`) before and after both the success
path and every refusal path; and asserts the exact `read()` size argument each loader's bounded read passes.
Its `RealMutationKills` class applies real textual source mutations to a private temporary copy of the whole
source tree and runs the actually-named tests against that copy in a subprocess (`python -m unittest
<test-id>`), reporting a genuine kill/survive result per mutation rather than an in-process claim. No broker
call is made and no live credentials file is read or referenced.
