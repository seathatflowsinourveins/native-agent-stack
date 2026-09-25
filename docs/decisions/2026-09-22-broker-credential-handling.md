# Decision: broker paper-credential file handling (2026-09-22)

**Decided by:** unit `pr4-gate-credentials`, catalog integration branch `claude/grand-catalog-20260922`; the coordinator mirrors a pointer into agent-lab.

**Scope:** `blueprints/us-equities/adaptive-paper/runner.py`'s `credentials(path)` only. `runner.py`'s caller
does not change; this decision only tightens the precondition on the env file that `--env-file` names before
it is opened. No broker call, no live credentials file, and no new secret store are introduced.

`market_research.py` (same directory) has its own, differently implemented `credentials(path)` that also
reads an Alpaca env file named by its own `--env-file` flag. **Closed 2026-09-24, hardened across four
same-day fix rounds** after independent, repeated Codex security review and an independent Claude
real-mutation/attack run (268 attack cases plus a live rename-exchange race with roughly 600k swaps, neither
finding an access-rule bypass; see `catalogs/us-equities/gates-20260922.json`'s `credential-handling` gate
note for the current, qualified guarantee): both loaders now call a shared
`blueprints/us-equities/adaptive-paper/credential_guard.open_verified()` for the ownership, mode (exactly
`0600` for the file), hard-link-count (exactly 1 for the file), ancestor-chain ownership/writability, and
outside-any-Git-worktree rules. These are bound to a `dir_fd`-chained traversal from `/`
(`O_DIRECTORY|O_NOFOLLOW` per ancestor, `O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_NOCTTY` for the file) so a symlink
substituted at any position -- an ancestor directory, not only the final file -- fails closed, normally with
`ELOOP` (final component) or `ENOTDIR` (a symlinked *directory* component, which is refined to the `symlink`
reason code via one extra, failure-path-only `lstat`, added in round 4, rather than left in the generic
`missing` bucket). Renaming an already-checked, victim-owned directory underneath an attacker-writable,
non-sticky ancestor (the round-2 Codex finding) no longer bypasses anything, because that ancestor itself is
refused the moment it is opened, independent of what gets renamed into it afterward or when -- every ancestor
up to but not including the immediate parent uses the OpenSSH `safe_path`/`secure_filename` model (owned by
root or `os.getuid()`; group/other-writable only if sticky), while the immediate parent (round-4: tightened
after round 3 accidentally let a bare `/tmp/file` load) uses a *stricter*, non-excusable rule -- owned by
exactly `os.getuid()` (root does not excuse it here) and never group/other-writable, no sticky exception --
so a private directory *under* `/tmp` still passes but `/tmp/file` and `/file` do not. `market_research.py`
keeps its original `O_NOFOLLOW` symlink-refusal behavior (`follow_symlinks=False`, applied per-ancestor-
component, not only the final file, and a lexical `..` component is refused outright rather than silently
collapsed -- collapsing it could skip inspecting an intermediate symlink); `runner.py` keeps its original
symlink-resolving behavior (`follow_symlinks=True`) so this runner's asserted `credential_file_permissions`
error-string prefix is unchanged. Every rejection raises one of a small, fixed set of path-free
`credential_file_permissions:<code>` reason codes (`credential_guard.REASON_*`, e.g. `:owner`, `:mode`,
`:hardlink`, `:worktree`, `:ancestor`, `:parent_owner`, `:parent_mode`, `:symlink`, `:not_regular`,
`:missing`, `:encoding`, `:size`) -- never a path, a basename, or upstream `OSError`/`RuntimeError` text; a
circular-symlink `RuntimeError` (which `Path.resolve(strict=True)` raises, not `OSError`, on the native
Python 3.12 runtime) and an embedded-NUL `ValueError` are both caught and normalized the same way. Round 4
also closed the one remaining reason-code inconsistency: an oversized `market_research.py` file now raises
`credential_file_permissions:size`, the same code `runner.py` already used, instead of the older
`invalid_credential_file`. Every such exception is also built and raised from code that is no longer inside
the `except` block that caught the original failure, specifically so Python never attaches that original
(potentially path-bearing) exception as `__context__`; `from None` alone does not achieve this, since the
interpreter re-populates `__context__` at the `raise` statement itself if one is still executing inside a
handler -- round 4 applied this same discipline to the ASCII check itself: both loaders now check
`raw.isascii()` on the *bytes* before ever calling `.decode("ascii")`, so the `UnicodeDecodeError` that
Python's decoder would otherwise raise (whose `.object` attribute holds the *entire* input, secret included)
is never constructed at all, rather than being raised-from-inside-its-own-handler with `from None` (which
does not clear `__context__.object`). The verified descriptor is closed on every failure path, including a
failure while wrapping it for reading: round 4 replaced a single `os.fdopen(file_fd, "rb")` call (whose
failure path risked a double-close -- if `io.FileIO`'s own constructor is what fails after accepting
ownership of the fd, CPython has already closed it, and a second `os.close()` either raises `EBADF` or
closes an unrelated, since-reused fd) with building `io.FileIO(file_fd, "rb", closefd=True)` first and only
closing that already-constructed *object* (never the bare integer) if wrapping it in a `BufferedReader`
subsequently fails. Covered by `tests.test_adaptive_paper_runner.CredentialFilePermissions` (existing, still
passing, plus symlink, hard-link, FIFO-does-not-hang, oversized-file, and non-ASCII cases -- the last two now
also asserting `__context__`/`__cause__` are `None`, and each FIFO case under a `signal.alarm` deadline that
itself fails via `self.fail(...)`, a genuine assertion failure, rather than letting the deadline's exception
escape uncaught), the existing `tests.test_adaptive_paper_runner.SharedCredentialGuardParity`, the existing
`tests.test_adaptive_market_research.MarketResearchCredentialFilePermissions` (wrong mode, wrong owner,
symlink, hard link, inside a Git worktree, missing file, a deadline-bounded FIFO, and a valid file), and
`tests/test_adaptive_paper_credential_race.py` -- note the real filename; an earlier round of this document
named a nonexistent `tests/test_credential_guard_race.py`. That file's `HookInjectedRaces`,
`AncestorRenameResistance`, `RootDirectoryOwnershipIsChecked`, `NoPathLeakInErrors`, `DotDotIsRejected`,
`FdOpenFailureCleanup`, `FdLeakOnRefusal`, `RootMarkerIsChecked`, `ForeignFileOwnerAloneIsRejected`,
`FstatNotPathnameStat`, and `BoundedReadIsActuallyBounded` classes exercise the round-2 and round-4 findings
specifically (a hook-injected mid-walk worktree marker, simulated foreign file/root/ancestor ownership via
per-fd `fstat`/`os.open` faking rather than a process-wide `os.getuid()` patch -- which would also fail the
parent-owner check and mask what is actually being tested -- error-content assertions that also check
`__context__`/`__cause__` are `None`, a real `os.listdir("/proc/<pid>/fd")` fd-count check around both
success and every refusal path, and a call-contract assertion on the exact `read()` size argument each
loader uses -- not only the outcome, since a static oversized fixture rejects identically whether the read
is bounded or not). Its `RealMutationKills` class replaces an earlier `MUTATION_KILLS` meta-test that only
patched in-process Python objects and asserted a hardcoded string-to-test-name mapping without ever running
those tests -- flagged by the round-2 Codex review as not establishing what it claimed to.

Round 4 (both reviewers, MEDIUM) found `RealMutationKills`'s *driver* itself, `tests/
_credential_mutation_driver.py`, over-counted kills: it treated any non-zero subprocess exit as a kill, so
`disable_worktree_check`'s named test -- which itself asserts `(repo_root / ".git").exists()` as a
precondition -- reported KILLED against a completely unmutated copy, because that copy (at the time) had no
`.git` at all. The driver now: runs `git init -q` in every copy; runs the named test id(s) on the **pristine,
unmutated** copy first and requires every one to report a plain "ok" (otherwise the spec itself, not the
mutation, is what is broken, and no kill/survive verdict is drawn); only then applies the mutation and
re-runs; and counts a kill only when a named test transitions to a genuine `unittest` "FAIL" (an
`assert*`-raised failure) -- never an "ERROR" (an exception escaping the test body, e.g. an import failure)
and never merely "the process exited non-zero", which the earlier version conflated. `tests/
test_adaptive_paper_credential_race.py`'s `MutationDriverSelfTests` class asserts this directly: an empty
mutation, an unrelated-import-breaking mutation, and a mistyped test id must each report "not killed" against
the driver's own logic. All fourteen mutations currently declared in `RealMutationKills.MUTATIONS` are killed
this way (see that test's printed report for the current list, generated fresh on every run, never a static
copy-pasted table); "does not hang" is asserted the same way -- the `O_NONBLOCK`-removal mutation makes the
FIFO test's own `signal.alarm` deadline fire, and that test converts the resulting timeout into an explicit
`self.fail(...)` so it registers as a real "FAIL", not an "ERROR" the stricter kill rule would then ignore.

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
4. **Every ancestor directory from `/` down through -- but not including -- the immediate parent, owned by
   root or by you, and group-/other-writable only if it also carries the sticky bit.** This is the OpenSSH
   `safe_path`/`secure_filename` model, applied to each ancestor as a *container*. It is what makes `/tmp`
   itself (sticky, world-writable) passable as an ancestor while an ordinary attacker-writable shared
   directory is refused outright, *regardless of what it contains or what gets renamed into it afterward* --
   closing a round-2 finding where only the immediate parent's ownership/mode were checked, letting an
   attacker who can write to an ancestor two or more levels up rename an already-checked, victim-owned
   directory into a location a `.git` ancestor would otherwise catch.
5. **The immediate parent -- the directory the file's own name lives in -- held to a stricter, non-excusable
   rule instead: owned by exactly `os.getuid()` (root ownership does not excuse it here) and never
   group-/other-writable, with no sticky-bit exception.** Round 3 relaxed this to the same rule as rule 4
   above, which meant a file sitting directly in `/tmp` (an acceptable *ancestor*, but never an acceptable
   *parent*) would load; round 4 tightened it back. This is why a private, caller-owned directory *under*
   `/tmp` still passes (it is independently checked by this rule, one level below `/tmp` itself) while
   `/tmp/file` and bare `/file` do not.
6. **Outside any Git worktree it is possible to detect from the file's own location, at the moment each
   ancestor is inspected.** `credentials()` walks the opened directory chain -- including `/` itself, not
   starting only at the first named component -- for a `.git` entry (directory in an ordinary clone, file in
   a linked worktree) and rejects the file if one is found at any ancestor, checked when that ancestor's own
   descriptor is opened (not from a pathname list computed once before any traversal happens, which a later
   rename could evade). This is a real, useful check, **not an atomic, held-for-the-duration guarantee about
   the location.** Two limits, not one:
   - A worktree configured purely through `GIT_DIR`/`GIT_WORK_TREE` environment variables or `core.worktree`,
     with no `.git` entry anywhere in the file's own ancestor chain, is undetectable by a file-local check
     and is **not** caught -- markerless worktrees of that shape remain fully out of scope. Likewise, a bind
     mount that makes a repository subdirectory appear at a path with no `.git` ancestor in its own mount
     namespace is invisible to this check; that requires mount authority (or an existing mount) to set up,
     and metadata checks do not categorically exclude virtual filesystems either.
   - Even for an ordinary `.git`-marked worktree, the check is a snapshot at each ancestor's own inspection
     time, not a lock held afterward. Another uid permitted to create entries in a sticky, world-writable
     ancestor (e.g. `/tmp`) can create a *new* `.git` entry there after that ancestor was already inspected
     and passed -- sticky permissions only stop that other uid from renaming or deleting an existing entry,
     not from adding a new one. This does not let that other uid bypass any file's own ownership/mode/
     hard-link checks, or relocate an already-opened, already-verified descriptor; it only means "outside any
     Git worktree" is a fact checked once per ancestor, at that ancestor's own inspection time, not a
     continuously-held property of the path as a whole.

   "Outside any Git worktree" here means "outside every worktree whose `.git` entry was an ancestor of this
   path at the time that ancestor was inspected, in this process's own mount namespace" -- it is not a claim
   that the file can never be committed, diffed, or swept up by every possible repository-wide scan.
7. **For `follow_symlinks=False` (`market_research.credentials()`), no `..` path component, ever.**
   Lexically collapsing `..` (the way `os.path.normpath` would) can select a different file through an
   intermediate symlinked component without ever refusing that symlink -- contradicting "a symlinked
   component is always refused". A `..` component is refused outright instead of normalized away.
8. **For `follow_symlinks=False`, every symlink component is refused, including one the operating
   system itself provides.** macOS's `/tmp` is a symlink to `/private/tmp`, and `/var` (hence
   `/var/folders/...`, `tempfile`'s default root there) is a symlink to `/private/var`; this rule
   refuses them the same way it refuses any other symlinked ancestor, with no exception for an
   OS-provided one. A caller in this mode must supply an already symlink-free path -- the documented
   credential store this loader is meant to be pointed at, a private path under `$HOME` (e.g.
   `~/.config/<tool>/paper.env`, `/Users/<name>/.config/...` on macOS), contains no such symlink, so
   this never affects normal use. It does mean a test fixture built from a platform's default
   temporary-file root must resolve it first (`os.path.realpath`) before exercising this mode;
   `tests/adaptive_paper_hermetic.py`'s `real_tmp_root()` is the shared helper both
   `tests/test_adaptive_market_research.py` and `tests/test_adaptive_paper_credential_race.py` use for
   every fixture root this mode's tests build. This guard is not weakened to trust a root-owned
   symlink here; the fix is in the fixtures, not the rule.

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
source tree and runs the actually-named tests against that copy in a subprocess (`python -m unittest -v
<test-id>`) -- first on the unmutated copy, requiring every named test to pass, then on the mutated copy,
counting a kill only for a genuine `unittest` "FAIL" (never an "ERROR", never merely a non-zero exit) --
reporting a genuine kill/survive result per mutation rather than an in-process claim. `MutationDriverSelfTests`
exercises the driver itself: an empty mutation, an unrelated-import-breaking mutation, a mistyped test id, and
(round 5) a test the driver's own copy makes report `"skipped"` must each report `"not killed"` --
`"skipped"` specifically as `"inconclusive"`, not silently folded into `"survived"` (a skipped test proves
nothing either way, which the driver's returned `killed` flag must not conflate with a real pass). No broker
call is made and no live credentials file is read or referenced.

## Round 5 (both reviewers, final small items)

- **`_is_symlink_component()`'s failure-path `lstat` escaped normalization.** It caught only `OSError`; a NUL
  byte in an ancestor directory component raised a bare `ValueError`, and a surrogate raised
  `UnicodeEncodeError` (whose `.object` attribute retains the ancestor's own name). Now catches `(OSError,
  ValueError, UnicodeError)`, so the already-sanitized `REASON_MISSING` code applies instead. Tested for both
  cases, asserting no path in the message, `.object`, `__context__`, or `__cause__`.
- **The `io.FileIO` double-close fix's own comment was wrong, and one real gap remained.** `io.FileIO(fd,
  "rb", closefd=True)` does **not** take ownership of `fd` until its constructor returns successfully --
  verified directly against CPython (a construction failure on a directory fd leaves that fd open) -- so the
  prior comment claiming CPython closes it on failure was incorrect, and `open_verified()` was leaking `fd`
  in that specific case. Fixed: `try: raw = io.FileIO(file_fd, "rb", closefd=True) except BaseException:
  os.close(file_fd); raise`; after that point only `raw` (never the bare integer) is closed. Two new tests:
  one patches `io.FileIO` itself to fail and confirms no leak; the other captures the constructed `raw` object
  when the later `BufferedReader` wrap fails and asserts `raw.closed` is `True` -- the deterministic way to
  tell a proper `raw.close()` apart from a bypassing `os.close(file_fd)` (`io.FileIO.close()` is implemented
  in C and never calls Python's `os.close()`, so counting `os.close()` calls cannot observe this at all).
- **The stricter immediate-parent rule (round 4) had no test that failed when it was reverted entirely.**
  Four new tests, each chosen so only the strict parent rule (not the generic, sticky-excused ancestor rule)
  can be what rejects it: a real 0600 file placed directly in the real `/tmp`; a simulated root-owned `0755`
  parent; a simulated sticky `1777` parent; and a bare `/file`.
- **The double-close fix had no test that failed when reverted.** The existing leak test patches
  `cg.io.BufferedReader`, which `os.fdopen`'s (or this module's own) failure path never uses to detect a
  *double*-close specifically -- only a leak. The new test above (`raw.closed`) is what actually distinguishes
  the two.
- **A symlinked directory component's `symlink` reporting (added round 4) had no direct test.** Added one.
- **Driver (Codex, low): a `"skipped"` result fell through to `"survived"`.** Fixed as described above; the
  docstring at the top of `tests/_credential_mutation_driver.py` also now notes that a `"FAIL"` can come from
  `setUp()`, not only the named test method's own body -- this driver does not currently distinguish those
  two sources of a `"FAIL"`, only that `unittest` marked the named id `"FAIL"` and not `"ERROR"`.

## Addendum (2026-09-25): macOS login Keychain through `secret run` as a second source

**Change.** `runner.py` and `market_research.py` take `--credentials {env-file,keychain-env}`.
`env-file` stays the default and is unchanged: the same `--env-file`, the same `open_verified()` rules and
reason codes, and `credentials(path)` keeps its default behavior for every other caller (order-throughput's
`capacity.py`, the native-faults harness, the sim fetchers). `keychain-env` reads `APCA_API_KEY_ID` and
`APCA_API_SECRET_KEY` from the process environment that `secret run APCA_API_KEY_ID APCA_API_SECRET_KEY --
python ... --credentials keychain-env` builds from the macOS login Keychain. The shared logic lives in
`blueprints/us-equities/adaptive-paper/credential_source.py`.

**Why.** The operator's hosts now include macOS, and the operator's standing rule keeps API keys in the login
Keychain and gives each only to the command that needs it. The "OS keychain" alternative above was deferred
"to a macOS-specific profile if one is adopted"; that condition now holds for this operator. Later sessions
can run the paper lane without a plaintext key file and without anyone retyping keys; the operator stores
them once with `secret set`. The env file stays because Linux/WSL hosts have no login Keychain, because it is
the reviewed and mutation-tested path, and because `docs/secret-storage.md`, `scripts/credential_status.py`
and the other `credentials(path)` callers depend on it.

**The earlier objection to environment variables.** It was aimed at keys exported into the invoking shell.
`secret run` exports nothing into the shell: it looks up each named item, exports it in its own process and
`exec`s the command, so only that command and its children receive the pair. The loader then removes both
names from its own `os.environ` as it reads them, so a child the runner starts afterwards does not inherit
them. Accepted residual exposure: the process's initial environment block stays readable, for the life of the
process, by processes of the same uid (`ps eww` on macOS, `/proc/<pid>/environ` on Linux) and by root. That
uid can already read the Keychain item through `security` while the login Keychain is unlocked, so this does
not widen access beyond it.

**Refusals (`keychain-env`)**, each a fixed code with no value or path, raised outside any `except` block and
checked in this order: a non-paper `APCA_API_BASE_URL` (below); neither name set (`keychain_env:missing`); only
one set (`keychain_env:partial`); a set but empty value (`keychain_env:empty`); a value that is not one
printable-ASCII token of at most 256 characters (`keychain_env:invalid_value`); an env-file loader marker
(`DIRENV_FILE`, `DIRENV_DIR`, `UV_ENV_FILE`, `PIPENV_DOTENV_LOCATION`, `MISE_ENV_FILE`) that names a location
inside a Git worktree, meaning a `.git` directory or file at it or at any ancestor, lexically or after
resolving symlinks (`keychain_env:worktree`). A location that cannot be inspected counts as inside a
worktree. `--env-file` together with `keychain-env`, or `env-file` without `--env-file`, is an argparse usage
error.

**Paper-only on both sources.** The base URL is pinned to `https://paper-api.alpaca.markets`, with an optional
trailing `/`. An `APCA_API_BASE_URL` in the process environment (both sources) or in the env file
(`env-file`, via `credentials(path, paper_only=True)`) with any other value is refused before any request:
`alpaca_paper_only:live_host` for `api.alpaca.markets`, and `alpaca_paper_only:not_paper_host` for everything
else, including an empty value, `http`, a port, userinfo, a path such as `/v2` and the paper URL in another
letter case. The transport already sends every request to the paper host (`PAPER_URL`, `paper=True`) and
`runner.load_config` already requires the paper endpoint. This rule makes a live setting in the shell or the file stop the run
before any request, where it would otherwise be ignored without notice.

**Limits.** A process-local check cannot tell a paper key from a live key. Because of the paper pin, a live key
fails authentication at the paper host and cannot place a live order. Provenance is detected only through the
markers listed above; `set -a; . ./.env`, `env $(cat .env)`, `uv run --env-file` given as a flag,
`docker run --env-file`, mise's `[env] _.file` and a dotenv loader inside a wrapper leave no marker and are
not detected. Like the file guard's worktree rule, the marker check runs once, at load time. A locked login
Keychain makes `secret run` prompt or fail, so this source suits operator-started runs, not unattended
hosting. `mover_runner.py` and the other `--env-file` consumers were not changed.

**Evidence that would overturn this addendum:** a way for another uid, a log or a crash report to obtain the
values from `secret run` or from this loader; unattended or multi-host hosting (see above); a second
consumer that needs shared, access-controlled retrieval.

**Evidence class:** `local_integration`. `tests/test_adaptive_paper_credential_source.py` (stdlib only, stand-in
values, no Keychain access, no network, no broker call) covers every refusal branch and asserts that each
error carries only its reason code with `__context__`/`__cause__` of `None`, that both names leave the
process environment, that the env-file default and `credentials(path)`'s default behavior are unchanged,
and that `runner.main()`/`market_research.main()` refuse before the first request (replaced by a stand-in).
Sixteen hand-applied source mutations of the new rules (worktree check, removal from the environment,
partial, empty, live-host code, process base URL for `env-file`, symlink resolution, fail-closed inspection,
both loaders' `paper_only`, duplicate base URL, the usage check, the `DIRENV_DIR` prefix, `UV_ENV_FILE` splitting
and the ASCII check) each failed this test module on a scratch copy. That run was ad hoc, and its output is
not retained as a receipt.
