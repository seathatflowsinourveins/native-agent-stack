# Decision: key management, part 1: every key of record in its 0600 store file, the kernel keyring as transport only (2026-09-29)

**Scope.** Where a provider key of record lives on a host, and the first change
of the D1 key-management design: before a planned kernel restart, the one key
that lived only in the kernel keyring (Tavily) moves into the file store. This
record extends [2026-09-24 secret storage](2026-09-24-secret-storage.md), whose
file store it keeps, and replaces the 2026-09-26 memory-only placement of
Tavily. The runbook is [`../secret-storage.md`](../secret-storage.md), the
inventory is
[`../../adoption/credential-inventory.json`](../../adoption/credential-inventory.json).
Later changes of the same design append dated sections at the end; the change
that adds the key injector amends this record. Built on branch
`claude/key-tavily-persist-20260929`, stacked on PR #481 (base `b40b3596`).

## Context

Verified on 2026-09-29 from source and tests. No value was read.

- The kernel keyring is memory only. `scripts/kernel_keyring.py` stores a
  `user` key named `native-agent-stack:<name>`, and a kernel restart erases it
  (on WSL2: `wsl --shutdown`, a Windows restart or update, or the idle VM
  stopping; [Lifetime](../secret-storage.md#kernel-keyring-transport-and-per-boot-spare-2026-09-29)).
  A restart of the workstation is planned for the evening of 2026-09-29.
- One inventory key lived only there: `tavily` (`tavily_api_key`, the
  operator's 2026-09-26 decision). The Alpaca paper pairs are in 0600 files;
  their keyring copies (`alpaca-paper-{1,2}-{id,secret}`) are duplicates that
  the restart erases, and this change leaves them alone.
- `kernel_keyring.py exec <name> <VAR> -- <command>` starts the command with
  its own environment plus exactly one credential-named variable
  (`_exec()`), so a writer started that way receives the key without an
  agent, a prompt or a command line seeing it.
- The guard hook's `check()` passes the exact chain command below at this
  branch's base; `tests/test_secret_path_guard.py` now pins it in `ALLOWED`,
  and `test_documented_keyring_commands_pass` checks the copy in the runbook.

## Dated reading of the user's instructions

Dated reading (2026-09-29, designer 1, for the coordinator):

- On 2026-09-29 the owner requested durable environment storage and seamless key handling so no key is lost;
  those owner statements state a rule for every key, as recorded in the coordinator's design brief.
  [Linux keyrings(7)](https://man7.org/linux/man-pages/man7/keyrings.7.html) establishes retention lifetimes, not the authority to change placement.
- These directions post-date the 2026-09-26 memory-only placement of Tavily and the owner's 2026-09-28
  instruction against file storage for keys supplied in chat. They had already reversed the latter for the
  Alpaca pairs by moving both into 0600 files; that recorded move remains separate from this reading.
  The restart plan and source/test findings establish why kernel retention is not the durable store of record.
- **Reading:** designer 1 interprets the later directions as moving Tavily to the existing 0600 file store,
  with the keyring retaining at most a per-boot spare. The root research unit had called the directions
  conflicting and left the move to the owner; this designer's reading resolves that conflict by recency
  and their stated no-key-loss goal, rather than presenting an upstream lifetime contract as the owner's decision.
  No key value was read; the move's execution evidence remains separate from this dated interpretation.
- **Overturn:** if the user restates memory-only for Tavily, the row reverts
  to `kernel_keyring`, now carrying the `memory_only_lost_on_restart`
  warning, and the file is removed by the user or by a tracked removal tool
  built at that time.

## Decision

1. **Store of record.** Every key of record is a `0600` file of
   `export NAME=value` lines in the `0700` store
   `${XDG_CONFIG_HOME:-$HOME/.config}/native-agent-stack`, as decided on
   2026-09-24. Tavily's row becomes `private_env_file` `<store>/tavily.env`,
   still optional; it is rotated with
   `tools/credentials/open_credential_terminal.sh tavily`.
2. **The kernel keyring is a transport only.** `kernel_keyring.py exec`
   hands a key to one command, and a key stored there is a spare that lasts
   until the next kernel restart. No key of record lives only there, and a
   required `kernel_keyring` row is an inventory error in
   `scripts/credential_status.py`, which `scripts/validate.py` and
   `set_credential.py` also run. New keys never go through the keyring.
3. **The one move from the keyring into a file**, run once by the
   coordinator after review, before the restart, from a checkout whose
   inventory already lists the file:

   ```sh
   python3 scripts/kernel_keyring.py exec tavily_api_key TAVILY_API_KEY -- python3 -I -S tools/credentials/set_credential.py tavily --from-env
   ```

   `set_credential.py --from-env`, built from the existing writer:
   - refuses unless both `sys.flags.isolated` and `sys.flags.no_site` are
     set, and never re-executes in this mode. The check runs before the
     module's re-exec block, because whatever ran at start-up ran beside the
     value: `-I` ignores `PYTHONPATH`, the `PYTHON*` variables and the user
     site directory, and `-S` also skips `site`, which runs the `.pth` lines
     of the interpreter's own `site-packages` even under `-I` (the
     coordinator's independent review of the first version, which accepted
     `-I` alone);
   - stores only an entry that declares exactly one variable, because a
     pair's provenance cannot be proven from an inherited environment;
   - pops the variable, then refuses an absent, empty or out-of-grammar
     value with the existing `encode()` rules;
   - is create-only: an existing name is refused before anything is
     written, even before `open_store()` could create the store or tighten
     its mode, and the final `os.link` fails with `EEXIST` rather than
     replace a file that appeared in between;
   - writes its temporary file as a dot-file (`.tavily.env.<16 hex>.tmp`),
     which a kill before the link leaves behind; the checker lists it as
     `undeclared_store_file` and never counts it as the stored key;
   - prints only `tavily: stored`.

   The store directory checks are the existing `open_store()`.
4. **The checker** reports a `kernel_keyring` row as `unchecked` with
   persistence `memory_only` and the warning `memory_only_lost_on_restart`,
   and lists, by name only, store files that no row claims
   (`undeclared_store_file`) and live `native-agent-stack:*` keys of the uid
   that no row claims (`undeclared_keyring_key`, from `/proc/keys`). Both
   are warnings.
5. **Not in this change.** A loader that reads the Tavily file, units that
   use such a loader, the Claude native mask and Codex proxy injection
   layers, and a canary harness belong to later changes of the design. The
   paper units and the paper env files are unchanged. Until a loader lands,
   Tavily works through the keyring copy until the restart and then has no
   key; Tavily is not the default web lane, so that gap is accepted.

## Alternatives considered so far

- **dotenvx `run`** (dotenvx 2.31.1, GitHub release of 2026-09-27; the
  binary's checksum matched the release's `checksums.txt`). *Measured* on
  2026-09-29 against this store format, with a synthetic canary in a scratch
  directory (the coordinator's session notes `kw/spike-dotenvx.md`, not in
  this repository): it loads `export NAME=value` lines, bare and quoted;
  redaction is opt-in (`--redact`) and covers raw values only; without `-q`
  its banner prints the env file's full path on stderr; and `run` executed a
  `$(...)` placed in a hand-edited value. It would still need a shim
  (inventory id to file, declared variables only, always `-q`, refuse values
  holding `$`, a backtick or a backslash) and a pinned per-platform binary,
  and it does not change where the key of record lives, which is the
  restart problem. Not adopted here; its redactor design is a reference for
  a later masker.
- **The kernel keyring alone** (`scripts/kernel_keyring.py`, the 2026-09-26
  placement). Memory only, so a key held only there is lost at every kernel
  restart and has no durable record. Kept as a transport and a per-boot
  spare.
- **systemd `LoadCredential=`** (systemd.exec(5), current documentation for
  systemd 262). It reads a credential from a file path or an `AF_UNIX`
  socket into the unit's read-only `$CREDENTIALS_DIRECTORY`, backed by
  non-swappable memory where possible. It needs a source file, so it changes
  how a unit receives a key, not where the key of record lives: mitigating
  only. The 2026-09-29 research sweep reports plain `LoadCredential=` working
  in user units on this host's systemd 255.4-1ubuntu8.17; this record does
  not re-measure that, and the paper units stay unchanged.

## Evidence class

- *Local integration*, synthetic values in temporary stores:
  `tests/test_credential_tools.py` (`StoreFromEnvTests`, twelve tests, and
  the second paper account's prefix hint) and
  `tests/test_credential_status.py` (the tavily file row, memory-only rows,
  the required-row error and both coverage lists). Each new behaviour failed
  before its implementation, except the dot-file name of the temporary file,
  which the first version already had and a mutation pins. Eight mutations
  of the writer are each caught by the intended test: abbreviations allowed,
  `os.replace` for `os.link`, re-execution instead of refusal, no pop, no
  isolation check, a temporary name without the leading dot, no pre-write
  existence check, and `-I` accepted without `-S`.
- *Controls*: a `sitecustomize` module on `PYTHONPATH` runs, and sees the
  variable, in a start without `-I`, and not under `-I -S`. In a throwaway
  venv, a `site-packages` `.pth` line records each interpreter start: a plain
  start records one non-isolated start that saw the value (so nothing was
  re-executed), `-I` alone records an isolated start that saw the value (the
  reason `-I` alone is refused), and `-I -S` records nothing and stores the
  file.
- *Upstream source and documentation*: the `/proc/keys` line format from
  linux v6.18 `security/keys/proc.c` (`proc_keys_show()`) and
  `security/keys/user_defined.c` (`user_describe()`); Python's `-I`
  (implies `-E`, `-P` and `-s`) and `-S`
  (<https://docs.python.org/3/using/cmdline.html#cmdoption-I>, `#cmdoption-S`);
  systemd.exec(5) for `LoadCredential=`.
- *Measured once in a session scratch directory, no committed receipt*: the
  dotenvx spike.
- *Not yet observed*: the chain on the host, the checker's `/proc/keys`
  parser against a real kernel's key list (the tests use a fixture in the
  upstream format), and the kernel restart itself.

## Known limits

- `-I -S` stops start-up code from a poisoned environment and from
  `site-packages`, but not a modified standard library: on a uv-managed
  Python under the home directory the same uid can write that too. That uid
  can already read the keyring and the store directly, so the threat model
  is unchanged.
- Popping the variable keeps it from any child of the writer, but Linux
  still shows the start-up environment in `/proc/<pid>/environ` to the same
  uid and root while the short writer runs, as for every `exec` command.
- A temporary file left by a kill holds the value until the operator
  deletes it; the checker names it, but nothing removes it automatically.

## Overturn

- The user restates memory-only for Tavily: the row reverts as in the dated
  reading above.
- A store that keeps a key through a kernel restart without a same-uid
  plaintext file and without a password or a per-session unlock (the user's
  2026-09-28 passwordless decision), for example `systemd-creds --user` with
  `LoadCredentialEncrypted=` on systemd 256 or later, is measured on this
  host: compare it with the 0600 file on restart survival, unattended use,
  same-uid readability and agent exposure.
- Any part of a value is found in a transcript, log or tool output after a
  `--from-env` run: stop using the mode, rotate the key, and type keys only
  through `open_credential_terminal.sh`.

## Boot receipt (2026-09-29)

The second restart safeguard of the same design (D1 PR-3), built on branch
`claude/key-boot-receipt-20260929`, stacked on the change above (base
`76ade87c`). The runbook is
[Restart check](../secret-storage.md#restart-check-2026-09-29).

**Decision.**

1. `scripts/credential_boot_receipt.py record` writes one value-free receipt
   per start of the user's service manager, to
   `${XDG_STATE_HOME:-$HOME/.local/state}/native-agent-stack/credential-boot/<sequence>-<UTC stamp>-<boot id prefix>.json`:
   a 0600 file in a 0700 directory, written as a `mkstemp` dot-file and
   linked into place, so no receipt is ever replaced. The 8-digit sequence
   number, one more than the highest present, is chosen and linked under an
   exclusive `flock` of the directory, so concurrent writers get distinct
   numbers; a name taken anyway (`EEXIST`) means choosing again, a bounded
   number of times. It prints one line of counts, which the runbook reads
   with `journalctl --user -u credential-boot-receipt.service -n 20 -o cat
   --grep='^credential boot receipt:'`: `-u` also shows systemd's own
   messages about the unit, and a finished oneshot logs one after the tool's
   line (review finding, 2026-09-29: `-n 1` could return it instead). The
   receipt holds the boot id, uptime, systemd version, linger
   (`loginctl show-user --property=Linger`), the checkout revision, the
   checker's rows reduced to ids, statuses, store kinds, path templates,
   states, findings and warnings, each file row's `lstat` mode, size and
   `mtime_ns`, the coverage names, the names of this uid's live
   `native-agent-stack:*` keys, and `claude_user_guard_matches_pin`. The
   checker observes each file itself, so the tool brackets that scan with
   one `lstat` just before and one just after it. A file whose device,
   inode, mode, size, mtime or ctime differs between the two changed while
   the checker looked; its row is `changed_during_record`, never `ok`, and
   `compare` counts it as not ok (review finding, 2026-09-29: a file
   removed between two separate observations had read as
   `ok -> ok, fingerprint gone`).
2. `compare` diffs the latest two receipts by state and by the names of
   changed fingerprint fields. Latest means the highest sequence numbers,
   never the clock: a WSL clock can step back after a Windows sleep or
   before its first time sync (review finding, 2026-09-29: a restart
   stamped 60 s earlier had reversed the order and read a deleted file as
   `missing -> ok`). Receipts named before sequence numbers sort before
   every sequenced one. It exits 1 when a required or optional file row
   that was `ok` is no longer `ok` or has no row, and 0 otherwise; a single
   receipt is reported as the baseline. It exits 2 without a readable
   receipt or when a receipt it reads lacks a field or holds one of the
   wrong type, as the baseline or the newer of two, with one line naming
   the receipt file only and no traceback (review finding, 2026-09-29).
3. `adoption/templates/systemd/credential-boot-receipt.service` runs `record`
   as a `Type=oneshot` wanted by `default.target`, from `@REPOSITORY@`, which
   the workstation renders to its live clone as it does for its other units:
   never the working checkout, whose revision moves, and never a build
   worktree, which a merge deletes. With linger on it runs at every
   user-manager start with no login and no unlock. It has no `Environment=`,
   `EnvironmentFile=` or `LoadCredential=` line. It is rendered by hand with
   the repository's existing `@REPOSITORY@` convention; no render tool was
   added.
4. `credential_status.py --client-guards` gains
   `claude_user_guard_matches_pin`: the sha256 of the installed user-scope
   guard against the guard's line in the checkout's
   `adoption/hooks/claude/SHA256SUMS`. The guard is opened with `O_NOFOLLOW`
   and hashed only when it is a regular file, so the check opens no store
   file even through a planted link; only the boolean leaves it.

**From the leak-path review.** The local receipt keeps each file's size,
which shows a truncated or emptied file. No printed, sanitised or published
form carries it, because a one-variable file's size gives its value's
length: `compare` names changed fields and never prints their values. No
content hash of any kind is recorded, because a hash of a short or guessable
value, such as the SEC contact identity, is an offline test for it. A
temporary or dot file that a killed writer leaves in the store is listed by
name in the `undeclared_store_file` warning, and so in the receipt.

**Alternatives.**

- A content hash per file would also catch a changed value of the same size
  and mtime, but it is the offline test above; rejected.
- A login hook or a `.profile` line runs only after a login, which the
  restart check must not need.
- `LoadCredential=` or an environment file for this unit: the unit needs no
  value, so it is given none.

**Evidence class.**

- *Local integration*, synthetic stores in temporary directories:
  `tests/test_credential_boot_receipt.py` (21 tests: the key allowlist;
  canaries absent in raw, base64, hex, percent-encoded and hashed forms from
  the receipt, the printed line, stderr and `compare`; modes; no replacement;
  the ok-to-missing, ok-to-unsafe and vanished-row regressions; a restart
  compared by name and state; the `-I` re-run; the unit pin; the runbook
  commands under the guard) and `tests/test_credential_status.py` (the pin
  boolean). Each new behaviour failed before its implementation, and twelve
  mutations of the tool are each caught by the intended test.
- *Text check of the unit*: its directive list is pinned, and
  `systemd-analyze --user verify` on a rendered copy exited 0 on this host
  (systemd 255.4). Nothing was installed, enabled or started.
- *Not yet observed*: the unit on the host, a receipt written at a real boot,
  and the restart itself. The Mac form, a `RunAtLoad` LaunchAgent, is
  documented, not run; `boot_id` is null there.

**Overturn.**

- A real restart where `compare` misreports a file that survived, or where
  the oneshot has not run before the first session: fix the comparison or
  the unit's ordering, and record the observation.
- A store that keeps keys through a restart without a same-uid plaintext
  file (the overturn above) replaces the file rows whose fingerprints this
  receipt compares.

## Part 4: the id-based key runner (D1 PR-4, 2026-09-29)

This section amends the record for the change that adds the key runner, in
two phases of one pull request series. Phase 1, this change, ships the
runner as **available**, with its limits stated. Phase 2, a later change by
another builder after the guard tightening lands, adds the runner's guard
model in `scripts/hooks/secret_path_guard.py` and only then makes the runner
the default path in `AGENTS.md`, the recipes and the runbook. The reason is
a check of 2026-09-29 against this checkout's guard: `check()` returned
`native_token_print` for `tvly auth` and `None` for
`python3 tools/credentials/credential_run.py tavily -- tvly auth`, and a
plain `tvly auth` prints a key's first eight and last four characters, which
masking cannot catch. Making the runner the default before the guard reads
it would reopen shapes that are refused today.

**Selection.** A stored key may be used through
[`tools/credentials/credential_run.py`](../../tools/credentials/credential_run.py):
`python3 tools/credentials/credential_run.py <inventory-id> [--only NAME]... -- <command> [args...]`,
or `--check`, which starts nothing. It is standard-library Python in the 3.9
grammar.
- It re-executes under `-I -S` before it reads anything.
- It resolves the entry through `scripts/credential_status.py`, and refuses
  engine-held, native, interactive and CI entries.
- It reads the `0600` file through a no-follow handle on the `0700` store
  directory, outside every Git worktree.
- It parses the file with `measure.py`'s `load_env_file` grammar, held to
  `set_credential.py`'s value grammar, so the writer and the reader share
  one grammar.
- The command gets only the entry's declared variables. The caller's copies
  of every inventory variable, `must_not_be_set` name and other entry's
  pointer variable (the path of that entry's store file) are removed first;
  the entry's own pointers stay.
- Each injected value is masked on both streams, raw and in its encoded
  forms: base64 and base64url interiors at three byte alignments; percent
  as `quote()` and `quote_plus()` write it, with `/` kept or escaped and in
  both hex cases; JSON plain, with `\/` and with `<`-style HTML
  escapes; and hex. Nested encodings, wrapped base64 and other escapers stay
  unmasked, and the runbook lists them.
- The masker keeps at most the longest form minus one byte, so a long run
  of overlapping matches comes out as several markers instead of being held
  whole.
- Output goes through non-blocking descriptors and a bounded queue in the
  relay's own select loop, so a consumer that stops reading cannot hold the
  runner past a shutdown signal or the 2 s drain deadline.
- What is left of the command's process group is ended (`SIGTERM`, 2 s,
  `SIGKILL`) on every way out of the runner, while the command is still an
  unreaped zombie that holds the group's number; the watchdog is stood down
  and the command reaped after that. On Linux a killed runner is answered by
  `PR_SET_PDEATHSIG` for the command and by a watchdog process for its
  whole group.
- It refuses a host whose `core_pattern` begins with `|` or `@`, one it
  cannot read, and a `RLIMIT_CORE` it cannot set to 0, with no override.
- The inventory's new optional `public_variables` names the variables that
  are injected unmasked, such as the Alpaca base URL. The schema rejects an
  entry that lists a name twice, or as both required and optional, and the
  masked set is computed from the validated schema, so a required variable
  is never public.
- The keyring stays a transport, units may run their program through the
  runner, and the paper units are unchanged. The Claude native mask and
  Codex proxy injection remain later layers.

The design and its limits are in
[Using a key](../secret-storage.md#using-a-key-available-2026-09-29).

**Not yet.** The runner's model in the command guard, and the flip of the
default path (`AGENTS.md`, the recipes, the runbook) that waits for it: both
are phase 2. Until then the runner is documented as available, with its
limits, and `recipes/tavily.md` keeps the keyring commands as its default.

**Built from these references, each re-read at its pin on 2026-09-29:**
- `scripts/kernel_keyring.py`'s env-only exec discipline;
- `blueprints/us-equities/pit-availability/measure.py:51-67`;
- dotenvx/dotenvx@278101db `src/lib/helpers/redactOutput.js`: longest
  first, the held partial tail, and never cutting a match;
- actions/runner@15231bed `ValueEncoders.cs` (base64 at shifted
  alignments, JSON and URI escapes) and `SecretMasker.cs` (overlapping
  matches merged);
- buildkite/agent@3345ee60 `internal/redact/redact.go` (`LengthMin` 6) and
  `internal/replacer/replacer.go`;
- dmno-dev/varlock@1b880652 `redact-stream.ts` (the 100 ms idle flush);
- Generalized-Labs/ironrun@b611c7ce `internal/redact/encodings.go` (hex,
  and percent forms in both cases).

**Read for the review's repair round, 2026-09-29:**
- torvalds/linux@v6.16 `fs/coredump.c`: a file pattern honours `RLIMIT_CORE`
  (L705), a `|` pattern sets it aside (L795-820), and so does an `@` core
  socket (L242-243 and L919);
- systemd/systemd@v257 `src/coredump/coredump.c`: no core is stored when the
  limit is below a page (L472-479), and the metadata still carries
  `COREDUMP_ENVIRON`, the process environment (L1458-1459).

**Read for the second repair round, 2026-09-29:**
- the man-pages `PR_SET_PDEATHSIG(2const)` page (man7.org): the setting is
  cleared for the child of a `fork`, so the signal reaches the command and
  not its children; it is sent when the thread that started the command
  ends; a set-user-ID binary clears it;
- python/cpython@v3.13.15 `Lib/multiprocessing/resource_tracker.py` (L8,
  L246-267, L425-429): a helper process that waits for the end of a pipe
  and ignores `SIGINT` and `SIGTERM`, the shape of the watchdog;
- bazelbuild/bazel@d2545923 `src/main/tools/process-tools.cc`
  `KillEverything` (L94-110): `SIGTERM` to the process group, a timeout,
  `SIGKILL` to the group, the order of the runner's group kill;
- krallin/tini@924c4bd6 `src/tini.c` (L472-475, L533): a supervisor that
  forwards the signals it receives to its child, or with `-g` to the child's
  group, except the ones in its own list (fault and job-control signals).
  The runner forwards seven, a narrower set on purpose;
- torvalds/linux@v6.16 `fs/coredump.c`: the `RLIMIT_CORE` of 1 that the
  kernel sets for a core-dump helper (L630) and the check that aborts a
  piped dump at that limit (L801-819).

**Read for the third repair round, 2026-09-29:**
- man7.org `wait(2)`: `waitid` with `WNOWAIT` leaves "the child in a waitable
  state; a later wait call can be used to again retrieve the child status
  information";
- torvalds/linux@v6.16 `kernel/pid.c` `__change_pid` (L349-369): a pid is
  released only when no task holds it under any of its four kinds (process,
  thread group, process group, session), so an unreaped command, a zombie,
  keeps its pid and its group's number;
- apple-oss-distributions/xnu@xnu-12377.121.6 `bsd/kern/kern_fork.c`
  (L972-974): a new pid skips one that is in use as a process, a process
  group or a session id; `bsd/kern/kern_exit.c` (L2969): a process leaves its
  group when it is reaped, so a zombie is still a member, as on Linux;
  `bsd/sys/proc_internal.h` (L767): `PID_MAX` is 99999;
- python/cpython `Modules/posixmodule.c`: `os.waitid` is compiled under
  `HAVE_WAITID && !defined(__APPLE__)` in v3.9.25 (L954), v3.10.0, v3.11.0
  and v3.12.0, and under `HAVE_WAITID` from v3.13.0; the 3.13
  `Doc/library/os.rst` adds "This function is now available on macOS as
  well".

**Candidates measured or read, with pins (2026-09-29):**

- **mise v2026.9.16** (commit `2184db81`). *Measured* in a scratch home
  with synthetic canaries (the coordinator's session notes
  `spike2/spike-mise-agentself.md`, not in this repository). Rejected:
  - it masks only under `mise run`, and a masked run passes no stdin (the
    child read 0 bytes);
  - a non-UTF-8 line drops the rest of stdout;
  - it injects a decodable copy of the injected environment as
    `__MISE_DIFF` (a task can close it with `unset __MISE_DIFF`, which does
    not change the rejection: a masked run still passes no stdin), and it
    expands `$` in values;
  - on a malformed line it prints the store path and the raw line with its
    value;
  - it has no id concept and no minimum value length.
- **agentself v0.2.4** (commit `418e7d79`; PyPI wheel sha256 `eea1f722…`).
  *Measured* the same way. Rejected:
  - it exits 0 when the command exits 7;
  - it returns output only after the command exits, inside one JSON object;
  - it imports a store file as a single value;
  - it has no release asset, only a 24-package Python wheel stack.
- **dotenvx v2.31.1**. *Measured* (part 1 above). Still the closest
  reference, and its streaming redactor is the masker's model. Not adopted,
  for part 1's reasons: redaction is opt-in and covers raw values only,
  its banner shows the store path, `run` executed a `$(...)` in a value,
  and it would still need a shim and pinned per-platform binaries.
- **ironrun v0.4.0** (published 2026-07-16; `main` at `b611c7ce`).
  *Observed* with the GitHub API. The closest agent-native design, but its
  default vault needs `secret-tool` on Linux, which this host lacks. Its
  policy runs fixed command ids with fixed argv, and whether its `envfile:`
  provider accepts `export ` lines is unverified. Its encodings table is a
  reference.
- **varlock 1.21.0**. It redacts by default, but `@import` needs file names
  that begin with `.env.`, it needs a schema file, and it injects a
  `__VARLOCK_ENV` blob. Its flush timer is a reference.
- **op 2.39.0, bws-v2.1.0, infisical v0.43.137, doppler 3.76.6, OpenBao
  v2.7.0, Vault v2.1.1, sops v3.13.3 with age v1.3.2, secretspec v0.21.1,
  fnox v1.36.0 and `pulumi env run`.** *Upstream documentation*, as the
  design's research recorded it; not re-read here. Each needs a token or an
  unlock on disk and a re-import, most do not mask, and sops cannot parse
  `export `.
- **`systemd-run --user` with `LoadCredential=`.** It delivers a file, not
  a variable, names the store path in the unit, does not mask, and does not
  exist on macOS.
- **The Claude sandbox credentials mask** (Claude Code 2.1.221 or later) and
  **Codex's network-proxy `inject_request_headers`**. Later layers only. The
  first covers sandboxed Bash in Claude and needs experimental settings; the
  second is undocumented and untested.

**One deviation from the build contract.** Amendment 4 of the contract says
that at EOF, or when the command is killed, a held tail becomes a
partial-redaction marker. The runner applies the amendment's own idle
threshold there as well: a held tail of 4 bytes or more is never printed
(on the idle timer, at EOF, on kill or at the drain bound), and one of up to
3 bytes is printed after 100 ms without output or at the end. The reason is
the first test run. Replacing every held tail turned the last `d` of any
output without a final newline into a marker, because every Tavily key
starts `tvly-` and its base64 starts `d`. With the literal rule, the output
of the same command would also depend on whether it paused before exiting.
The constant `SHORT_TAIL_MAX` restores the literal rule. A mutation of it is
caught by `test_flushes_an_unterminated_tail_at_eof`.

**A second deviation from the build contract.** The 6-byte minimum length
applies to masked names only. A public variable (a base URL that the entry
lists in `public_variables`) is injected whatever its length, because it is
not masked, so the rule that keeps a short value from masking ordinary
output does not concern it. `test_short_values_are_refused` checks a
one-byte public value.

**Repair round (2026-09-29).** A read-only GPT-6 review at effort max of the
first head (`e437a361`) returned seven findings. Each was reproduced with a
synthetic value in a temporary store, or failed a new test first, and is
fixed with its own test:
1. *High.* The runner was documented as the default path before the guard
   models it. It is now documented as available, with its limits (above).
2. *High.* `RLIMIT_CORE` 0 does not stop a crash collector. The runner
   refuses a `core_pattern` that begins with `|` or `@`, one it cannot read,
   and a limit it cannot set, with no override. The `@` case goes beyond
   the review's wording, on the kernel source above. The residual is a
   same-uid debugger, `ptrace` or `/proc` read.
3. *Medium.* The common percent and JSON encoders write forms the masker
   did not register: `quote()` keeps `/`, `quote_plus()` writes `+`, PHP
   writes `\/`, Go writes `\u003c`. All are needles now. What stays
   unmasked (nested encodings, wrapped base64, other escapers, fragments,
   and what the second round added) is listed in the runbook, and a test
   reads that list, prints each form as it is and checks that the list
   names it.
4. *Medium.* Overlapping matches were held without a bound: 126,976 bytes
   after 31 chunks of six identical characters. The masker keeps at most
   the longest form minus one byte, and a long run comes out as several
   markers. A scratch fuzz of 40,000 dense-overlap streams in four
   chunkings (not committed, so not reproducible from this repository) is
   recorded as having left the same unmasked bytes as the whole-buffer
   masker. The committed check that stands for it compares the two outputs
   with the markers removed: it shows that the same bytes are left
   unmasked, not how many markers there are or where they stand.
5. *Medium.* Blocking writes let a stalled consumer hold the runner past
   `SIGTERM` (2.7 s, until it read). Output is now non-blocking behind a
   256 KiB queue per stream. The tests assert bounds: a stalled consumer
   is not waited for after `SIGTERM` (under 1.5 s), and the runner exits
   between 1.5 s and 10 s after the command's exit (the 2 s drain). Single
   manual measurements gave 0.1 s and 2.1 s.
6. *Medium.* The schema accepted a required variable that was also
   optional and public. It now rejects an overlap and a repeated name, and
   the masked set comes from the schema module.
7. *Low.* A stdin closed at start was reopened on `/dev/null` and closed
   again by the exec (`EBADF` in the command, not end of file). It is
   inheritable now.

**Second repair round (2026-09-29).** A second read-only review of the
repaired head (`3275b47d`), by an Opus security reviewer with synthetic
probes, found no path that prints a whole masked value in a form the runner
claims to mask, and confirmed six of the seven fixes above. It left the
items below. Each code item failed a new test first.
1. *Medium.* The command could outlive the runner. It runs in its own
   session; only `SIGINT`, `SIGTERM` and `SIGHUP` were forwarded; a `SIGKILL`
   of the runner, or a default-fatal `SIGQUIT`, `SIGUSR1`, `SIGUSR2` or
   `SIGALRM`, ended only the runner; and descendants still running after
   the 2 s drain were left running with the key in their environment. The
   runner now ends the command's process group on every way out
   (`SIGTERM`, 2 s, `SIGKILL`, reap), forwards the four other signals, and
   on Linux the command asks the kernel for `SIGTERM` when the runner dies.
   One step goes beyond the review's wording. The parent-death signal
   reaches the command and not its children (the kernel clears it for a
   `fork`), and the test that failed first showed a descendant writing its
   marker file after a `SIGKILL` of the runner, so a watchdog process ends
   the whole group when the pipe it shares with the runner closes. It has
   the shape of CPython's `multiprocessing` resource tracker.
2. *Low.* The runner removed `variables`, `optional_variables` and
   `must_not_be_set` of every entry, but not the `pointer_variables` of the
   others, so a command run under one id could load another entry's file
   through a pointer that the shell profile sets (`ENV_FILE`,
   `SEC_CONTACT_ENV`). It now removes every entry's pointer except the ones
   the selected entry declares.
3. *Low, tests.* Two rules had no pinning test, and a mutant of each
   survived a copy of the previous head's test module. A planted entry that
   declares `LD_PRELOAD`, `PYTHONPATH` or another reserved name is refused
   before any store is read. One socket end as the runner's stdin, stdout
   and stderr must stay blocking for the command, which the terminal test
   could not show (a terminal is never made non-blocking). Both are pinned,
   with mutants that are caught.
4. *Docs.* The four limits below are stated once here and once in the
   runbook.
5. *Corrections.* The runbook says which signals are forwarded instead of
   saying that signals pass through. The first round's sentences on the
   list of unmasked forms, the fuzz and the timing are reworded (above). The
   tests named after "every real encoder" are renamed, because the PHP and
   Go JSON forms are string-replacement models of what those encoders
   write, and only the Python encoders are executed. The deviation on public
   names is listed (above), and so is the note on the mise spike.
6. *CodeQL.* The pull request's code scanning reported
   `py/clear-text-storage-sensitive-data` (high) at
   `tests/test_credential_run.py` line 141, the `path.write_bytes(...)` of
   the test helper that writes a synthetic store file. The SARIF data flow
   of the analysis (`gh api` with `Accept: application/sarif+json`) starts at
   a variable named `secret` at line 152 that holds a `fake()` value: a name
   heuristic on a fixture. The variable is renamed, with no suppression
   comment. CodeQL was not run locally, so CI is the check; if the alert
   stays, it is a verified false positive for the coordinator to dismiss
   with a dated comment.

**Third repair round (2026-09-29).** A targeted read-only GPT-6 review of the
watchdog and the group kill returned two findings. Each was fixed with a test
that failed first.
1. *High.* The runner's final `killpg` and the watchdog kept only the number
   of the command's process group and acted after the command had been
   reaped. Nothing holds a number once its last process is reaped, the kernel
   may give it to a stranger, and a signal to it then reaches the stranger's
   group. The runner now learns that the command exited without reaping it
   (`os.waitid` with `WNOWAIT`), signals the group only while the command is
   still a zombie, whose pid, and with it the group's number, nobody else can
   take, then tells the watchdog to stand down, and reaps the command last.
   The watchdog therefore acts only when the runner died without telling it.
   Signalling is refused once the command is reaped, and the signals the
   runner forwards are blocked while it reaps, so that no handler runs
   between the reap and its record. A default `SIGCHLD` is set first: an
   inherited ignored one makes the kernel reap the command at once, with no
   zombie and no status. `kill(-pgid, 0)` cannot tell that a group is empty
   while the command's zombie is in it (a zombie is a member until it is
   reaped, on Linux and in XNU), so the group's live members are counted from
   `/proc`, and a command that left nothing behind is not signalled at all.
   Failing first (the previous head, with only the new constant declared):
   the recorded events showed `killpg` on a reaped command, in the runner's
   final cleanup and in the probes after it. What remains is stated in the
   runbook and below: if the runner dies before it stands the watchdog down
   and init reaps the command before the watchdog acts, a recycled number is
   theoretically possible on a host with a small pid space, and the
   watchdog's prompt reaction bounds the window.
   *Platform correction.* The brief took `os.waitid` for available on macOS.
   It is only from CPython 3.13 (sources above), and macOS has no `/proc`, so
   the pinned cleanup is Linux-only. Where it is not available the runner
   sees the exit by reaping the command and never signals the group after
   that: on macOS the descendants of a command that has already exited are
   left running, which the second round's fix had ended (with the hazard this
   round closes). A failure inside the runner, while the command is
   unreaped, still ends the group there. That is a recorded loss on macOS.
   None of this was run on macOS.
2. *Medium.* The command's pre-exec code ran with a copy of the runner's
   handlers. `forward()` only records a signal, so a parent-death `SIGTERM`
   that reached the command between the parent-pid check and the exec was
   queued in the copy instead of ending the command, which then ran (the
   reviewer's probe: pause after the check, kill the runner, resume: exit
   42). The hook now puts every signal the runner handles back to its default
   and clears the inherited signal mask before it arms the signal, and keeps
   the parent-pid check after arming. The tests hold the forked command at
   the two stages through a module function that their launcher replaces (no
   environment switch): killed while held after the check, the command is
   gone at once and never runs; killed while held before arming, it ends by
   the parent-pid check and never runs; started with a signal blocked, it
   sees default handlers and an empty mask. Failing first, with the hold in
   place and the reset absent: the command outlived its runner, and its
   handlers were the runner's.

**Limits recorded on 2026-09-29**, once each here and once in the runbook:
- *The non-blocking flag* is set on the open file description of an
  inherited pipe or socket, so other writers on that description (`xargs -P`
  siblings, background jobs, a unit's other processes) can see `EAGAIN` for
  the length of a run. With two runners on one pipe, the first to exit makes
  the pipe blocking under the second. The fix (`poll` and writes of at most
  `PIPE_BUF` for pipes, `send` with `MSG_DONTWAIT` for sockets, or a writer
  thread that can be abandoned, and never a flag flipped on an inherited
  description) is planned for the hardening change before the default-path
  flip.
- *"Cannot hold the runner"* holds only for the pipes and sockets the
  runner can make non-blocking. A terminal, a pty, a regular file, a
  description shared with stdin, and any sink that falls back to direct
  writes use blocking writes, and can hold the runner past a signal.
- *Unmasked forms.* The list gains a value broken by wrapping or by other
  bytes between its parts (`xxd` or `hexdump -C` columns, `fold`, wrapped
  table cells, colour codes, two writers on one stream), hex with
  separators, a value with a single quote that the shell requotes (`set -x`,
  `printf %q`), and anything the command writes to an inherited read-write
  stdin, which never passes through the relay. The rule: a value is masked
  only where a whole form of it appears unbroken in one stream.
- *The command's lifetime.* A `SIGKILL` of the runner before the watchdog
  has started leaves only the parent-death signal. If the runner dies
  before it stands the watchdog down and init reaps the command before the
  watchdog acts, a recycled group number is theoretically possible on a host
  with a small pid space (macOS numbers stop at 99,999); the watchdog's
  prompt reaction bounds the window. The pinned cleanup, which signals the
  group only while the unreaped command holds its number, is Linux-only (no
  `os.waitid` on macOS before Python 3.13, and no `/proc` there); elsewhere
  the runner never signals after the reap, and a descendant of a command that
  already exited is left running. A descendant that leaves the process group
  (`setsid`, `setpgid`) is out of reach of the group kill and of the
  watchdog, and so is a set-user-ID command. Only Linux has been run; the
  watchdog has not been run on macOS. A same-user debugger or `ptrace` is
  out of scope.

**Unverified lead, not a claim (2026-09-29).** At an `RLIMIT_CORE` of exactly
1 the kernel aborts a piped core dump: in torvalds/linux@v6.16
`fs/coredump.c` a limit of 1 is the recursion guard (L801-819, reported as
"RLIMIT_CORE is set to 1, aborting core"), and L630 sets it for the dump
helper itself. The runner might therefore set (1, 1) instead of (0, 0) and
work on a host with a piped `core_pattern` instead of refusing it. It has
not been tested against a real collector, and the refusal stays until it
is.

**Evidence class.**
- *Local integration*, synthetic values in temporary stores:
  `tests/test_credential_run.py` (92 tests) and the schema tests in
  `tests/test_credential_status.py`. The runner tests were written first
  and failed to import the missing tool; the schema tests failed on the
  missing field; each test of a code repair failed before its fix (the
  second round's items 1 and 2 and the third round's findings 1 and 2, each
  on the head before it). The pinning tests of the second round's item 3
  passed at once, so a mutant of each rule was run against a copy of the
  previous test module first, and survived it; the third round's test of
  the parent-pid check passed at once too, and its mutant is caught. In a
  scratch mutation run, each of 96 mutants (32 of the first round, 29 for
  the first repair round, 19 for the second, 16 for the third, one rule
  removed or changed each time) failed its intended test, and the files were
  restored by sha256; the script clears the cached bytecode around each
  mutant, because a same-size mutant written in the same second as an
  earlier compile is otherwise served the earlier code (one such run reported
  a survivor that a rerun caught). The tests start the runner
  through a test-only launcher on a host whose real `core_pattern` pipes
  crash dumps, which CI runners commonly do; the two tests of the real
  re-execution skip there, and one test checks the real tool against the
  host's own pattern.
- *Upstream source*, read at the pins above on 2026-09-29, and macOS ps(1)
  at apple-oss-distributions/adv_cmds@6bed8737.
- *Measured once in a session scratch directory, no committed receipt*: the
  mise, agentself and dotenvx spikes, the check of this checkout's guard on
  `tvly auth` behind the runner, one run of the 92 runner tests under
  uv-managed CPython 3.9.25 and 3.14.7 on Linux (all pass, with
  `DeprecationWarning` an error in the test process), a run of the whole
  runner module with `PINNED` forced off in the test process and in every
  runner start, which is how a platform without `os.waitid` and `/proc`
  (macOS before Python 3.13) would run it (92 tests, 11 skipped: the 9 that
  need the pinned cleanup and the 2 of the real re-execution, as on a host
  that pipes crash dumps; the rest pass), and one run of coreutils
  `timeout -k` against the runner with a command and a descendant that both
  ignore `SIGTERM`, in a synthetic store: `timeout` killed the runner, and
  both were gone about 3 s after it returned; and the watchdog's reaction,
  25 runs on an idle host, from the pipe's closing to the death by
  `SIGTERM` of a sleeping member of its group: median 1.3 ms, largest
  1.4 ms (the figure behind "promptly").
- *Not yet observed*: the runner on macOS, including the Command Line Tools
  `python3` and the watchdog, a
  real key through it (the canary harness is a later change), a host that
  pipes crash dumps (the refusal is tested with pattern files, not with a
  real `systemd-coredump` crash), a harness escalation other than the
  `timeout -k` run above (the tests send `SIGKILL` to the runner directly),
  a process-id wrap-around that recycles a group's number (the residual
  above is reasoned from the kernel sources, not reproduced), and the
  runner's guard model and the default-path flip, which are the second phase
  of this change.

**Overturn.**
- A maintained upstream tool does all of the following, measured with the
  same probes (split write, EOF tail, kill, non-UTF-8 output, stdin, exit
  code, malformed line): it runs one command with one id's declared
  variables, masks raw and encoded forms on both streams while streaming
  with a held tail, reads this store format by id without an unlock, and
  passes stdin, the exit code and non-UTF-8 bytes through. Then adopt it and
  retire the runner.
- ironrun's `envfile:` provider is shown to read `export ` lines and run
  ad-hoc argv with masking on both streams: compare it head to head.
- The Claude sandbox mask leaves experimental status: add it as a layer.
  The runner stays for Codex, OmniRoute lanes and units, which run no
  guard.
- A kernel and collector pair that honours `RLIMIT_CORE` 0 for a piped or
  socket `core_pattern` is shown on a real crash, with no environment in the
  journal: drop the refusal for that pair.
- Any part of a value is found in a transcript, log or tool output after a
  runner use: stop that use, rotate the key, and record how it leaked.

## Status at the end of the 2026-09-29 session

This section is the record of what stands, what does not, and why; the sections above are the design and its evidence.

**Merged to main (squash commits).**

| Change | Pull request | Commit | Evidence class |
| --- | --- | --- | --- |
| Interactive `claude` launches start at effort `max` through the ecosystem launcher (opt-out `claude --effort xhigh`); decision record `2026-09-29-max-default-effort.md` | #483 | `a452a0ab` | native runs read from the client's transcripts (receipt `claude-max-default-effort-20260929`), launcher tests on Linux and macOS CI |
| Numbered credential pointers (`PAPER_ENV_FILE_2`) are read as pointers; `alpaca-paper-2` inventory entry | #481 | `c26800f3` | local integration (guard tables) |
| Tavily key persisted: create-only `set_credential.py --from-env` (`python3 -I -S`), memory-only checker rows, undeclared-item warnings | #490 | `556fd816` | local integration; the one host write ran once after the merge |
| Boot receipt: value-free record of the key store at every user-manager start, `Type=oneshot` unit from the live clone | #495 | `bc83a5f8` | local integration; unit verified with `systemd-analyze`; baseline receipt recorded on the workstation |
| Key runner `credential_run.py` (id-based injection with masking) and `public_variables` | #497 | `5cfa2400` | local integration (92 tests, 96 mutants caught); one real use below |

**First real use of the runner (2026-09-29, one call, local observation).** With the real Tavily store file, `credential_run.py tavily --check` printed `tavily: ok; would inject TAVILY_API_KEY (masked)` and `credential_run.py tavily -- tvly auth --json` printed `{"authenticated": true, "method": "env", ...}`: the key reached `tvly` through its environment only, and no value appeared in either output. This supersedes the sentence in Decision point 5 that Tavily has no key after a restart: the store file survives a restart and the runner is the loader.

**Not done, with the reason and the next step.**

1. **Guard tightening (branch `claude/guard-launchers-20260929`, not merged).** Models `systemd-run` and its family as launchers (a reader they start was not inspected, so `systemd-run --user --pipe --wait cat "$PAPER_ENV_FILE"` returns the pointed-to file; the gap is recorded in `tests/test_secret_path_guard.py` since #481), reads `$(...)` and backticks inside double quotes, refuses macOS `ps -E` forms and `systemctl show-environment`, fails closed on an internal error and on a command over 200,000 characters. Two independent GPT-6 reviews of two designs found block-to-allow regressions each time (a general quoted-here-document data rule: six blocking findings; a canonical `git commit` idiom exemption: six blocking findings and two timeouts). The resolution is a tightening-only guard: the exemption is removed, a shared work budget bounds tokenisation and launcher analysis, and `ps -C` keeps both the procps and the macOS reading. Nothing merges before a third verification finds no block-to-allow regression. Until it lands the installed guard stays the merged pin. Known friction after it: a commit message or pull-request body whose prose has command-like lines is refused (write it with the editor tool and pass `git commit -F <file>`).
2. **Guard model of the runner, interpreter here-documents, OmniRoute credential routes, user-manager environment writes, keyring store from a literal (planned change "K4").** Brief and executable acceptance table (`guard_oracle.py` phases `injector`, `routes`, `heredoc`) are recorded with the session; the interpreter here-document false positive (`set(a) | set(b)` in a `python3 -` body read as the `set` builtin) was reported by three sessions. Until it lands, `credential_run.py <id> -- printenv` is allowed by the guard and protected only by masking, and the runner is documented as available, not the default path.
3. **Canary proof harness (branch `claude/key-canary-20260929`, not merged).** Two review rounds and one repair round: the second GPT-6 review still found false-zero paths (evidence reused after a failed rerun, a failed scan retry leaving an older pass authoritative, missing or partial captures, an unenforced restart gate, undecoded compression framings, SQLite WAL and extensionless databases, filename and symlink coverage, exclusions wider than the protected paths, malformed Loki pages, sampling that drops other consumers' hits). A harness whose zero can be produced by a broken scan is worse than none, so no proof claim is made. Next step: a much smaller tool for exactly the acceptance the user set (a per-consumer canary and a zero-hit grep with positive controls over the named sinks) with one classifier that refuses unless every required check has a fresh result bound to the run.
4. **Restart acceptance.** The procedure is "Restart check" in `docs/secret-storage.md`; the R0 baseline receipt exists. The restart is the user's action, after 20:00 ET and with the trading lane's confirmation.
5. **Codex profile hardening** (`ignore_default_excludes = false`, shell snapshots off) is not done; it is measured (Codex 0.157.1: credential-named variables reach the shell tool by default).
6. **OmniRoute** returns decrypted provider credentials to an unauthenticated loopback caller on `GET /api/providers/client` and `GET /api/settings` when `requireLogin=false` (source-read by the gateway lane at builds `5fc47d970` and `c3fa5a15e`, not executed). The real fix belongs to the gateway lane; the guard rule is part of item 2 and only covers Claude's Bash tool. Superseded on 2026-09-30 by "OmniRoute management API (decision, 2026-09-30)" below: `/api/settings` returns settings secrets rather than provider connections, the anonymous surface is much wider than these two routes, and containers on this host reach it.

**Selections that stand, with the comparison that would overturn each.** Store of record: the `0600` files (overturn: a keychain or sealed store that needs no unlock and survives the restart, measured on both workstations). Injector: built from cited reference designs (dotenvx `278101db`, actions/runner `15231bed`, buildkite/agent `3345ee60`, varlock `1b880652`, ironrun `b611c7ce`) after mise v2026.9.16 and agentself v0.2.4 failed the same measured requirements (Part 4). Effort: the launcher flag, not an environment variable or a saved level (overturn conditions in `2026-09-29-max-default-effort.md`). Proof tooling: none accepted yet (item 3).

## OmniRoute management API (decision, 2026-09-30)

**Finding.** Source reads only; no request was sent to either gateway. Four independent checks confirmed it: three claim-verification slices and one control-coverage review. Both gateways run upstream `release/v3.8.51` at `2f42a9ac1` plus local carries. The carries touch none of the files cited here, whose blobs are identical to upstream, so every citation below is `diegosouzapw/OmniRoute@2f42a9ac1`.

With `requireLogin=false`, the management policy admits an anonymous `auth-disabled` subject on every management path that is not always-protected (`src/server/authz/policies/management.ts:261-266`; `src/shared/utils/apiAuth.ts:472`). On those paths `requireManagementAuth` returns no error (`src/lib/api/requireManagementAuth.ts:59-61`). An anonymous loopback caller then gets:

- **Reads:**
  - `GET /api/providers/client` returns every connection with its decrypted `apiKey`, `accessToken`, `refreshToken` and `idToken`, and with unsanitized `providerSpecificData` (`src/app/api/providers/client/route.ts:5-15`; `src/lib/db/providers/lazyConnectionView.ts:149,177-189`).
  - `GET /api/settings` returns every stored non-internal setting (keys starting with `_` are skipped, `settings.ts:287`) except the password and two session keys. That includes the decrypted `oidcClientSecret`, and `skillsmpApiKey`, `cliproxyapi_api_key`, `qdrantApiKey`, `quotaStore.redisUrl` and `deepHealthToken` whenever they are set (`src/app/api/settings/route.ts:230-289`; `src/lib/db/settings.ts:154,287,295-297`).
  - `GET /api/settings/cache-config` returns the semantic-cache embedding API key and the Redis URL (`src/app/api/settings/cache-config/route.ts:50-51,86,109`). Upstream open issue #14484 reports the same echo.
  - `POST /api/sync/tokens` followed by `GET /api/sync/bundle` returns the whole decrypted credential bundle (`src/app/api/sync/tokens/route.ts:28-29,77-79`; `src/lib/sync/bundle.ts:68-89,112-127`).
  - `GET /api/cli-tools/keys` returns the raw OmniRoute keys.
  - `GET /api/oauth/cursor/auto-import` returns the host's Cursor OAuth tokens (`src/app/api/oauth/cursor/auto-import/route.ts:15,22-25`).
  - Several `cli-tools/*-settings` readers return whole client configurations: `claude-settings` returns `~/.claude/settings.json` including `env` (`src/app/api/cli-tools/claude-settings/route.ts:56,66`) and `codex-settings` the raw `config.toml` text (`codex-settings/route.ts:120,171`); `omp-settings` returns an API key (`omp-settings/route.ts:91`). Not every reader does: `cline-settings` returns five selected fields (`cline-settings/route.ts:77-83`).
  - The `providerSpecificData` keys `cookie`, `cookies`, `access_token`, `clientSecret` and `token` pass even upstream's own sanitizer for `/api/providers` (`src/lib/providers/requestDefaults.ts:327-371`).
- **Writes:**
  - `POST /api/keys`, `POST /api/keys/[id]/regenerate`, `POST /api/cli/tokens` and `POST /api/relay/tokens` mint credentials, manage-scope ones included, and return them.
  - `PATCH /api/providers/[id]` can set a provider's `baseUrl`. The gateway then sends that provider's stored credential to the new host (`open-sse/executors/base.ts:417-418`; upstream's own comment at `:428-430` names the keyless case).
  - With login off, `POST /api/settings/require-login` stores a password hash of the caller's choosing, which locks the operator out (`src/app/api/settings/require-login/route.ts:92,125-127`).

**Correction to item 6.** `/api/settings` returns settings secrets, not provider connections; the provider credentials are on `/api/providers/client`. The builds item 6 cites, `5fc47d970` and `c3fa5a15e`, resolve neither locally nor upstream, so the finding is re-confirmed at `2f42a9ac1`.

**Who can reach the API:**

- **Same-uid processes.** This includes:
  - Claude's Bash tool.
  - Codex shells: the host Codex configuration runs `sandbox_mode = "danger-full-access"`.
  - Windows processes. With mirrored networking they reach WSL's `localhost`: on this host `wslinfo --networking-mode` prints `mirrored` (<https://learn.microsoft.com/en-us/windows/wsl/networking>). Through `\\wsl$` they also read distribution files as the default user (<https://learn.microsoft.com/en-us/windows/wsl/file-permissions>).

  Every such process can already read the gateway's data directory: the store, `server.env` and the CLI token salt. No HTTP control changes what they can reach.
- **Containers.** Rootless Docker on this host runs with `DOCKERD_ROOTLESS_ROOTLESSKIT_DISABLE_HOST_LOOPBACK=false`, set in the user unit `docker.service` at line 33. Upstream's default in `dockerd-rootless.sh` is `true` (moby/moby@a46e6fa7 `contrib/dockerd-rootless.sh:23-24,170-173`). So every container whose network routes through the rootless daemon's RootlessKit network, and that has no separate isolation, reaches host-loopback ports as `10.0.2.2` ([OpenHands isolation record](2026-09-28-openhands-resolver-isolation.md)); a container with network mode `none`, such as the OpenHands grader, does not. On 2026-09-30 the Harbor benchmark lane reported reproducing this with a canary listener on another loopback port; that is a peer report, and this record retains no receipt of it. A container that runs model-written or third-party code is an untrusted local process, which meets the overturn condition of the keyless posture in [the account-pool record](2026-09-27-omniroute-account-pool.md), decision 5.
- **Agent browsers.** The browsers this ecosystem runs are agent tools, not a person's desktop browser: agent-browser 0.38.1 (vercel-labs/agent-browser, `manifests/stack.json` row `agent-browser`), and playwright-cli 0.1.21 on Playwright 1.64.0-alpha and playwright-test 1.63.0 (microsoft/playwright-cli, microsoft/playwright; rows `playwright-cli` and `playwright-test`), which drive Chrome for Testing from the Playwright cache on this host. They run as same-uid processes, but a page they load is third-party code, and under WSL's mirrored networking that page can address the gateway at `localhost`.
  - Measured on 2026-09-30 (receipt `agent-browser-lna-20260930`): Chrome for Testing 153.0.8010.12, launched by agent-browser 0.38.1, by Playwright 1.63.0 and directly, refused fetch, image and iframe requests from a page placed in the public address space to a loopback listener, with no permission grant, in all six launch configurations; with the override off, or with Local Network Access disabled, the same requests arrived. A public third-party page opened by these agent browsers therefore cannot send a request to the gateway, so agent browsing of public pages stays within the same-uid boundary.
  - Not covered by that measurement: main-frame navigations and popups (Chromium's Local Network Access does not gate them), pages in the private address space, a tool or user that grants the permission, a launch that disables `LocalNetworkAccessChecks`, other Chromium versions, and the manifest pin playwright-cli 0.1.21 on Playwright 1.64.0-alpha, which was not found installed.
  - Upstream's origin validator rejects cross-site and DNS-rebinding origins, but only for dashboard-session subjects (`src/server/authz/pipeline.ts:418-421`; `src/server/origin/publicOrigin.ts:177-179,243-245`).

**Options compared:**

- **(a) Upstream's control, `requireLogin=true`.**
  - It is the only control that closes the whole management surface for every caller.
  - It needs a stored password, `INITIAL_PASSWORD` or OIDC. Without one, a loopback caller can still write `requireLogin: false` (`src/shared/utils/apiAuth.ts:474-478,511-515`; `src/app/api/settings/require-login/route.ts:90-122`), and the dashboard login needs a stored hash.
  - On 2026-09-28 the owner ruled out a login/password, allowed an environment key if needed and required closing container exposure without a password. That direction is a deployment constraint; the [WSL networking contract](https://learn.microsoft.com/en-us/windows/wsl/networking) does not authenticate shared loopback, and this record claims no verified isolation merely from the instruction. No login or password setup is applied here.
- **(b) A local redaction carry.**
  - It removes direct reads on the patched routes only, and cannot close the writes above for a loopback caller.
  - The surface spans about fifteen routes, in files upstream edits weekly: `routeGuard.ts` three times and `settings/route.ts` once in the week to 2026-09-29.
  - For same-uid callers it adds nothing beyond accident prevention.
- **(c) A command-guard rule.** Accident prevention for Claude's Bash tool only.
- **(d) A documented posture.** It states the boundary and its residuals.
- **An origin-validator carry.** Upstream's validator would be widened to anonymous subjects on unsafe methods, with a Host check added on reads. It is a small carry built from in-repo references. It closes browser writes, plus rebinding reads from older browsers and from navigations, but does nothing for containers or same-uid callers.

**Decision.** (d) plus (c), with one load-bearing rule and no gateway change now.

1. **Trust boundary.** The anonymous management API is accepted only while every process that can reach host loopback is a same-uid process the user runs, and every workload that runs model-written or third-party code is either stopped or has verified isolation (rule 2). An exposed untrusted workload invalidates the boundary at once, whether or not it could adopt isolation later: it is stopped until it is isolated. Within the boundary, the reads and writes above are same-uid residuals, like the data directory itself.
2. **Container rule (load-bearing).**
   - A container that runs model-written or third-party code must have no route to `10.0.2.2`, nor to any other host address that reaches the gateway ports.
   - If it needs a model, it reaches the gateway only through a proxy that passes the client API and refuses `/api/*`.
   - References: the OpenHands lane's O1 (a Docker `internal: true` network plus a proxy; [isolation record](2026-09-28-openhands-resolver-isolation.md)), and Harbor v0.23.0's own egress control (`[environment] network_mode = "allowlist"`: a sidecar proxy plus nftables with an allowlist of public hosts; harbor-framework/harbor@v0.23.0 `src/harbor/environments/docker/docker.py`). The Harbor benchmark lane reported applying it on 2026-09-30; that is a peer report without a retained receipt here, and the lane's own records carry its acceptance.
   - Daemon-wide `DISABLE_HOST_LOOPBACK=true` is not chosen, for the isolation record's reasons: it cuts off the proxy and the memory services, and binding the gateway elsewhere would expose it beyond loopback.
   - Each container lane applies the rule to its own workloads.
3. **Guard rule (planned in K4; not yet built, accepted or installed).** Once K4 is built, accepted and installed after window W, Claude's command guard refuses:
   - a command that sends a request under `/api/` to the gateway ports (`20128`, `20129`) on `127.0.0.1`, `localhost`, `[::1]`, `10.0.2.2` or `host.docker.internal`, except an allowlist of read-only paths the repository documents. The allowlist is derived so that the documented-command replay stays at 0 newly blocked;
   - the matching `omniroute api ...` and `omniroute sync ...` CLI forms.

   It will also treat both live data directories, `~/.local/share/omniroute` and `~/.local/share/omniroute-fw`, as credential stores. Until then the installed guard covers neither (`scripts/hooks/secret_path_guard.py`, `HOME_CREDENTIAL_STORE`).
4. **No gateway change now.** Neither carry is applied, and the gateway operator keeps the current settings. Any gateway apply stays on the Gate A owner's timing.
5. **Operator hygiene after window W, at the gateway operator's discretion.**
   - Take a metadata-only inventory of the OmniRoute keys, `oma_` tokens, sync tokens and relay tokens created while management was anonymous.
   - Use the OmniRoute CLI on the host, not `curl` from an agent shell: `GET /api/keys` shows the first 8 and last 4 characters of each key.
   - Revoke any the operator does not recognise.

**Verification.**
- For the container rule: a canary listener on a host loopback port (never a gateway port) must record no connection from a task container that tries `10.0.2.2` and the host's other addresses on that port, observed on the listener side, because a transparent egress proxy may accept a TCP connection before it enforces its policy; the proxy's refusal of `/api/*` is checked against a throwaway upstream, never a live gateway; and a model call through the proxy must succeed.
- Never verify with an HTTP request to `/api/*` of a live gateway. The OpenHands probe P0 (`blueprints/runtime-workers/openhands/e2e/netprobe.py:90-94`) sends one to `/api/settings`; it should become a TCP-only probe or target a throwaway instance.
- For the guard rule: K4's oracle phase `routes` and the documented-command replay.

**Residual exposure:**
- Every same-uid process, including Windows processes of the user's account, holds full administrative control of both gateways and every stored provider credential.
- The agent browsers' Local Network Access was measured for public-address-space pages only; main-frame navigations, private-address-space pages and permission grants are not covered.
- Until the container rule is verified for a workload, that workload must not run model-written or third-party code.

**Overturn:**
- A workload that runs model-written or third-party code found without verified isolation: it is stopped at once. If it cannot be isolated, the source-reviewed `requireLogin=true` control with a password is required to close the management surface; changing the dated passwordless deployment constraint remains a separate user-owned decision.
- Upstream ships a non-interactive management credential that an anonymous loopback caller cannot disable, for example key-only management with the bootstrap write closed: adopt it.
- An agent-browser, Playwright or Chromium change, a launch that disables `LocalNetworkAccessChecks` or grants the loopback permission, or a measured request from an untrusted page (including a navigation or a private-address-space page) reaching a loopback listener: re-measure, and if a request reaches the listener, apply the origin-validator carry, which closes rebinding reads and cross-site writes for every browser.
- A gateway port bound beyond loopback, a second OS user on the host, or a gateway reachable from the LAN: the posture no longer holds.

## Codex shell snapshots that recorded the messaging token (done, 2026-09-30)

On 2026-09-29 the sink inventory found 19 files under `~/.codex/shell_snapshots` that each declared `CLAUDE_CODE_MESSAGING_TOKEN`. The scan read names only. Codex writes the exported environment of the process that launched it into these files (`codex-rs/shell-command/src/shell_snapshot_exports.rs` at `rust-v0.157.1`).

At 2026-09-30T03:00Z a names-only rescan walked `~/.codex`, `~/.local/state`, `~/.local/share`, `~/code`, `/tmp` and `/var/tmp`, without following symlinked directories and skipping `node_modules`, `.git`, `__pycache__`, `.venv`, `venv`, `site-packages` and Claude's own `shell-snapshots`; directories or files it could not read were skipped without a count. It found 222 `shell_snapshots` directories holding 12 files it could read.
- Only 2 of those files still declared the variable, both in `~/.codex/shell_snapshots`, with modification times of 2026-09-27T02:19Z and 04:45Z (an earlier scan of that one directory printed both). No open descriptor to either was observed among the processes whose descriptors were readable.
- The other 17 were already gone. Codex's own three-day snapshot retention is the likely remover (`codex-rs/core/src/shell_snapshot.rs:105` at `rust-v0.157.1`), but the removal was not observed.

After an announcement to the live peers, the enumerated path list was compared byte for byte (`cmp`) with the two literal paths, and the two files were deleted by their literal paths at 03:02:25Z.
- A rescan found 0 files declaring the variable among the files it could read.
- A names-only listing of `~/.codex` taken before and after showed exactly those two entries removed.
- No file content was printed.

Where to act next:
- Codex's `shell_snapshot` feature is on by default (`codex-rs/features/src/lib.rs:1008-1011` at `rust-v0.157.1`).
- The host's base configuration and its OmniRoute profile turn it off, and so does the packaged GPT-6 lane home.
- A Codex home whose configuration leaves it unset still writes snapshots. Item 5 above (Codex profile hardening) covers the repository templates after window W.

Overturn: any new snapshot file with a credential-named `declare -x` line. That moves the Codex profile change ahead of window W, subject to the Gate A owner.

## Status update (2026-09-30)

- **Guard tightening** (item 1, PR #511, not merged).
  - Head `dc33b48a`; guard sha256 `a70a056f`, equal to its `SHA256SUMS` pin.
  - The third GPT-6 verification ran at the pre-repair head. It found one blocking regression, a procps personality selector passing the clustered `ps` loosening. It also found one high finding, inherited from the installed guard: four store-path patterns backtracked and timed out the hook at 10 s.
  - One repair round followed:
    - it removed the `ps` loosening;
    - every command is also read as the installed guard reads it, and is refused when either reading refuses;
    - the four patterns became linear scans.
  - A fourth verification found no command the installed guard refuses that the new guard allows.
  - Its two remaining findings go to the next guard change, because only one repair round is allowed:
    - a descriptor-deduplication case that the installed guard also allows;
    - a documentation note.
  - Receipt: `guard-k3-verification-20260930`.
  - The merge and the host reinstall wait for the Gate A owner to close window W, because the frozen check `hooks.carriers_match_repo` compares the installed hooks with main.
- **K4** (item 2). These counts are status reports from the lane's review records, which are not retained in this repository; each PR carries its own receipt. The build contract had its first independent review, by GPT-6: 1 blocking and 6 high findings. The largest were a delimiter-suffix gap in the interpreter here-document form, a second loosening the amendments had not authorised, and an unbounded gateway matrix. Version 2 is being written with one gateway matrix, one loosening and an independent reference recognizer for the tests.
- **Canary proof tool** (item 3). Draft 2 of the contract took one Opus review round (4 blocking findings, fixed). A GPT-6 review then found 7 more blocking false-clean paths:
  - sink bytes reaching the coordinator's memory;
  - a pass still standing after a failed retry;
  - an unstable file set;
  - a Git metadata gap;
  - a gzip-plus-BOM gap;
  - SQLite schema text;
  - SQLite URI parsing.

  Draft 3 is being written with a two-process boundary and a stable-file-set rule.
- **Claude OAuth token for headless runs.**
  - A credential window stores the token from `claude setup-token` in the kernel keyring as `claude-oauth-token` (transport only; a kernel restart erases it). Commands receive it through `kernel_keyring.py exec claude-oauth-token CLAUDE_CODE_OAUTH_TOKEN -- <command>`.
  - Its variable is not yet a secret name in the guard, so K4 adds it and an inventory entry. `set_credential.py` can then persist it.

## Part 5 — Canary proof continuation (2026-09-30)

The earlier parked harness remains unaccepted. The replacement is
`canary_proof.py` plus a contained `canary_scan_worker.py`, isolated probe,
native two-stage workflow and null-output packaged lane wrapper. This is a
build and synthetic qualification, not a production proof. The operational
procedure is [Canary proof](../secret-storage.md#canary-proof). Acceptance of
the window still requires K4 installed, explicit Gate A window closure,
independent final Astra/Opus review, workstation containment and P5 rehearsal.
No production canary, credential, transcript, journal or database was used by
this build. The coordinator registers evidence pins separately.

The selected scanner remains upstream ripgrep 14.1.0, commit
[`e50df40a1967708b9781486b1c017e48040bceb0`](https://github.com/BurntSushi/ripgrep/tree/e50df40a1967708b9781486b1c017e48040bceb0).
Its standard printer's only-matching records carry exact matched literal
bytes behind a known label/NUL; its stats count completed file searches.
`crates/printer/src/standard.rs:837,923,1064,1698,1760`,
`crates/core/main.rs:94,126,461` and `flags/hiargs.rs:232,728` establish the
failure/count/encoding assumptions. Quiet mode has a documented match/error
exception, so this tool never uses quiet mode. Installed `/usr/bin/rg` is
14.1.0; the PATH scanner can be newer, so resolve/hash absolute executables.
15.2.0 (`e89fff89ac9af12e8d4ce9d5fd07beb408ca730f`) is a source-reviewed output
grammar, not executed: the runtime accepts it with its own stats terminator, and
its only test is a hand-written stats fixture. The executed version is 14.1.0.
A release lookup is currency evidence, not scanner acceptance.

Compression uses GNU gzip 1.12, bzip2 1.0.8 and xz 5.4.5 producers reading
held descriptors through their supported `-d -c` interfaces; lzma uses xz's
explicit `--format=lzma`. These versions are encoded in setup FACT records.
No implicit package installation or ripgrep --search-zip path is adopted.
The supplied scanner comparison considered grep/ripgrep, gitleaks, TruffleHog
and detect-secrets; it favored exact literals with explicit controls and
failure accounting for this known synthetic corpus. That comparison is
supplied research, not a new benchmark. Kingfisher/Titus were not evaluated
and are not asserted inferior.

Containment reuses `adoption/tools/ecosystem-bounded-run` unchanged, with its
enforced memory/pids/CPU scope and finite RuntimeMaxSec/TimeoutStopSec backstop.
Upstream systemd v255 is
[`db11bab38ccf1ed257f310d29070843d4c58ea01`](https://github.com/systemd/systemd/tree/db11bab38ccf1ed257f310d29070843d4c58ea01):
`src/run/run.c:620,962,1721` and `man/systemd.scope.xml:113` document inherited
scope descriptors and lifetime semantics. A scope cannot use --pipe/--pty.
Util-linux v2.39.3
[`2da5c904e18fdcffd2b252d641e6f76374c7b406`](https://github.com/util-linux/util-linux/blob/2da5c904e18fdcffd2b252d641e6f76374c7b406/sys-utils/setpriv.c#L1055)
arms PR_SET_PDEATHSIG before exec. Each upstream executable started by the
worker uses setpriv; stdin is DEVNULL, a held descriptor or an owned pipe.
No lifeline pipe is used (C13): parent death reaches each child through
PR_SET_PDEATHSIG, and whatever a signal misses through the scope's
RuntimeMaxSec plus TimeoutStopSec. The pre-arming race and setsid/TERM-ignoring
descendants rely on that verified finite scope backstop. CI's exec stub tests
direct process death only and cannot establish cgroup/grandchild acceptance.

Repository reuse is explicit: credential_run's encoded_forms, Masker,
Command/end_group, inventory and core checks; set_credential's encode and
create_exclusively; credential_status's inventory/metadata/guard pin helpers;
and credential_boot_receipt's private directory and create-only publisher.
The store-worktree helper performs ancestor metadata checks, not an external
Git call. Guard pin checking stays inside a setup child and never uses the
client_guards reader. Forbidden upstream/repository files stay unchanged.

Git v2.43.0 `Documentation/git-cat-file.txt`, `git-verify-pack.txt`,
`git-fsck.txt`, `gitrepository-layout.txt` and setup.c provide the logical
framing/physical verification interfaces. SQLite's
[URI filenames](https://www.sqlite.org/uri.html),
[schema table](https://www.sqlite.org/schematab.html),
[read-only WAL](https://www.sqlite.org/wal.html#read_only_databases) and
[table_list](https://www.sqlite.org/pragma.html#pragma_table_list) provide the
database interface. CPython's subprocess/os/struct/sqlite3 interfaces and
POSIX/Linux no-follow/nonblocking descriptors complete the local integration.

The seven draft-3 repairs have executable negative oracles:

| Repair | Resulting contract / oracle |
| --- | --- |
| Parent byte exposure | Every raw channel stays in worker/dumper; unrelated header/name/target/diagnostic sentinels audit coordinator fds, payloads and artifacts |
| Old pass survives setup crash | Fsynced request precedes mkdir/union/control/plan; SIGKILL and setup errors supersede old passes |
| Unstable handoff/file set | Retain the original prewalk tuples/lists; held-fd and ctime/route/final-rewalk fixtures detect replacement and same-inode writes |
| Git objects subtree exemption | Scan .keep/metadata raw; reconcile every loose/pack member with exact logical enumeration; unknown/orphan/index-only payload is incomplete |
| Compression plus BOM | One decoder stream fans raw and BOM-first/encoded-control views; absent branch or decoder failure is incomplete |
| SQLite schema hidden | Empty UTF-16/overflow schema/default/view/trigger/name canaries are found logically even when raw bytes miss |
| Wrong SQLite URI/inode | Escape %, ?, #; verify PRAGMA path and actual opened main fd against held inode; replacement is incomplete |

Continuation testing exposed another false-zero route: a regular file replaced
by FIFO after held handoff could fail the first subpass but be called a harmless
special on retry. Hard type failures now remain incomplete and are independently
asserted by F-M1b/c. The scanner still reads the held original inode; that alone
is not stability acceptance. Likewise, reading current scan metadata into the
prewalk record could erase the original identity; ST1–ST5 retain and reconcile it.
Mutation acceptance preserves each historical fault family and adds the draft-3
repairs, nonce/ledger/branch/request obligations: `tests/canary_mutants.py`
(amendment C3) holds draft 2's 65 rows adapted to this design, one row per G6
repair, the protocol/branch/request rows and two continuation repairs. A kill
requires a passing pristine named test followed by its actual assertion failure,
never import, syntax or unrelated fixture failure. Where two layers guard the
same fault (the worker and the coordinator, a hard-coded key path and the
inventory, a post-walk and the END seal), a one-layer mutant survived its first
run; each layer then got its own oracle or the row mutates the fault as a whole,
and the table says which. Raw returned logs and patches are retained outside the
repository until a future evidence PR.

Evidence classes remain distinct: installed help/version, fresh pinned source
retrieval, synthetic local integration, independent kernel process observation,
workstation scope enforcement and live consumer/provider execution. The repair
round used the first four inside its sandbox: 141 tests ran there, 128 passed
and 13 skipped (12 native-scope cases and the then-uninstalled K4 guard rule),
separate FIFO and boundary runs passed 9 and 12 tests, and all 135 mutants were
killed by their named assertions after 88 passing pristine runs. Earlier fixture
repairs and partial runs establish no scope acceptance. The coordinator's
outside-sandbox runs on the workstation supply it. At `4d8404d5`,
`python3 -I tests/test_canary_proof.py -v ContainmentRealScopeTests` ran 12
tests in 79.171 s, OK, exit 0. At `a07b7a24` (every canary-named file
byte-identical to `4d8404d5`, the tree stacked on the K4 guard and other merged
changes) the full unit file ran 141 tests in 1059.136 s, OK, 0 skipped, and
`python3 -I tests/canary_mutants.py --json` reported 135/135 killed after 88/88
passing pristine runs, with the repository inputs unchanged. The credential and
guard suites had one failure, by design: `test_host_profile_copy_is_verbatim`
compares the installed host copy, which differs until reinstall. The whole
repository suite remains with the coordinator. The 2026-10-01 re-check round's
own run is recorded at the end of this part. This repair runs no upstream test
suite and does not relabel these local fixtures as upstream
acceptance. Network retrieval worked through the installed public context-mode
channel despite shell-network failure. Returned source pins and hashes are
retained with the build handoff; no credentials or host paths enter public
evidence. Foreign shared /tmp metadata is preserved; the synthetic launcher
limits worktree ancestry checking to its owned fixture, without a production
environment override or credential-runner edit.

Draft 3 estimates 650 coordinator lines, 1,150 worker lines, 1,800 aggregate
and 2,800 test lines (probe/workflow/wrapper excluded from aggregate). After the
2026-10-01 re-check repairs the implementation has 1,834 coordinator lines and
2,114 worker lines, 3,948 combined. The coordinator accepted that deviation for
the required coverage and containment logic in the one repair round. The
3,632-line permanent test file also exceeds its original ceiling because the
reviews require the missing cases, independent observations and paired mutants;
that test-size deviation remains reported for coordinator disposition. The
782-line mutation runner is allowed separately and excluded from the test-line
ceiling.

The repair corrects seven reviewed false-clean paths: discovered Git indirections
and damaged Git layouts, WAL families without a logical main scan, incomplete END,
selection-aware symlink coverage, the prepared cursor seal, final journal entry
termination, and virtual shadow ownership. The damaged Git layouts corrected are
exactly these, each refused as incomplete in `RepairTests`: a `.git` directory
missing HEAD or missing refs stays a logical store by its name (as does a
directory with `objects/` and one of HEAD or refs), so Git's own validation
refuses it (`producer_stderr` in the fixtures); a discovered gitfile whose target
is outside every covered root, or is not a logical store by those rules, refuses
as `git_indirection_unplanned`; and, since the 2026-10-01 re-check, a directory
the walk reaches directly with object-store shape but no logical store (a loose
object `objects/<2 hex>/<38 or 62 hex>`, or a pack or index file in
`objects/pack`, with no HEAD, refs, `*.git` name or gitfile) refuses the same
way, whether or not its files are selected. Zlib data outside a Git store and
outside that shape stays a stated residual. SQLite shadow ownership follows
`sqlite/sqlite@version-3.45.1` `ext/fts5/fts5_main.c` (`fts5ShadowName`),
`ext/fts3/fts3.c` (`fts3ShadowName`) and `ext/rtree/rtree.c` (`rtreeShadowName`).
Unknown virtual modules refuse logical completeness.

The cleanup design required Astra/Max review after a bounded Sol repair: native
runner exit 143 alone cannot prove the scope was stopped because its trap
suppresses stop errors. The accepted design keeps the worker alive after END,
signals the still-owned runner group to invoke its scope-stop trap, releases
the terminal acknowledgement pipe, and checks kernel cgroup emptiness before
reaping. FACT 12 supplies only a worker PID and
the numeric native scope suffix. The coordinator validates membership against
its own runner PID and reads containment metadata only. This follows
[systemd v255.4 cg_is_empty_recursive](https://github.com/systemd/systemd-stable/blob/v255.4/src/basic/cgroup-util.c#L927):
`cgroup.events` populated 0 or disappearance is empty; all other failures refuse.
Synthetic acceptance is distinct from native scope acceptance, which the
coordinator's outside-sandbox runs supply on the workstation: 12
`ContainmentRealScopeTests` OK at `4d8404d5`, and the full unit file (141 tests,
0 skipped) OK at `a07b7a24`.

Correction log for this round: the reviewed prior claims of complete acceptance
were too broad. Header sentinels now plant exactly what the oracle checks; FIFO
tests observe the intended child's open FIFO inode and sleeping reader through
`/proc`. The installed kernel calls that wait channel `anon_pipe_read` (older
kernels use `pipe_read`). Consolidating the journal parser initially collided
with the scanner parser attribute; the independent export parser fixes that.
Strict END rejection initially prevented legitimate stability retries; an
incomplete END now retains a nonzero failure reason while inconsistent counts
still fail the protocol. Removing M2 control reports exposed a missing format
obligation; an explicit numeric routing check now binds per-format controls.
An intermittent post-END shutdown timeout exposed reliance on signal delivery
to the terminal worker; releasing its pipe after signalling the runner fixes
that wait while retaining the cgroup-empty gate. A deterministic fixture also
ignores TERM and requires pipe release. The version-stage FIFO fixture initially
matched `--version` inside setpriv's nested command, blocking the outer wrapper
before the native executable set PDEATHSIG. Exact argv matching fixes the
fixture, and the observer checks the complete version-helper argv. Astra/Max
confirmed this against [util-linux v2.39.3 setpriv.c](https://github.com/util-linux/util-linux/blob/v2.39.3/sys-utils/setpriv.c#L1055);
the failed fixture is not evidence of a production parent-death regression.
The pinned-leader review also found inherited `SIGCHLD=SIG_IGN` could automatically
reap children before cleanup. Both parents now reset SIGCHLD immediately before
their owned Popen, matching `credential_run.run_command`. Isolated regressions
require two successful `waitid(WNOWAIT)` observations and the original exit status;
both reset-removal mutants are killed. This follows Linux execve/wait semantics
([man-pages 6.19](https://man7.org/linux/man-pages/man2/wait.2.html)). The first
mutation run additionally exposed a cleanup fixture whose child accepted TERM
and an equal-count rename caught too early by the held-file identity check.
The child now ignores TERM before announcing readiness; the rename occurs just
before the postwalk. Their dedicated mutants now exercise the intended oracles.
The historical builder substitution under section 16/C14 remains a recorded
deviation. Existing commit attribution is preserved, as the coordinator directed.

One classifier selects latest requests, binds attempts/roots/ledgers, retains
sticky hits and rejects missing/error/stale checks. Requested U/comparison
become obligations until a fresh complete request replaces them. Cleanup's
absence fact does not stale evidence. Loki always remains proxy_unverified
inside tool receipts; equality is an external P5 window record only. Transcripts
are excluded all-or-nothing unless confirmed at prepare. Every claim identifies
absent roots, exclusions, application transformations, special content, remote
copies, process memory and scanner-side children's memory, plus metadata
quiescence limits (backward clocks, shared mappings, privileged/same-uid changes
and writes after the check). No macOS port or restart canary is asserted.

Reconsider the choice when a maintained scanner demonstrates equivalent failure
propagation, descriptor/file-list inputs, logical SQLite coverage or decoder
repairs against this same suite; when a supported runner test-store option
removes the narrowly authorized synthetic production-store exception; or when
P5 reveals a new required encoding/container. Installing zstd is a separately
announced post-W host change plus a decoder contract/fixture update. Replacing
the scanner based on popularity or a newer release alone is insufficient.

### Re-check round (2026-10-01)

An independent read-only Opus re-check of the repair round (code at `a07b7a24`)
confirmed 37 of 42 dispositions. It found one remaining false-clean path, one
record-validation defect and documents that claimed more than the code. This
round repairs them:

- Objects-only Git store reached directly (high). A directory with Git
  object-store shape but no HEAD, refs, `*.git` name or gitfile got no Git
  handling: its zlib loose objects went to the plain view, so a canary inside
  them read as clean. `Walk.entry` now refuses that layout with the gitfile
  refusal's reason, `git_indirection_unplanned` (`object_shaped` uses the names
  `Store.payload` counts, so a 62-hex SHA-256 loose name qualifies too).
  `RepairTests.test_objects_only_store_reached_directly_refuses` walks Git-made
  loose objects (the run's canary inside one zlib object, in no raw form), an
  index-only `objects/pack` and a packed store; mutant R-OBJONLY removes only
  the check. The refusal is a second layer for damaged `.git` directories, so
  R-02 (store recognition narrowed to HEAD, objects and refs together) survived
  its first run. The damaged-store fixture now also asserts that such a
  directory is still counted as a store (`git_stores` 1), and R-02 is killed by
  that assertion.
- Request-level `inventory_unreconciled` (medium). Sink rows accepted it, but
  the request's reasons did not: when a busy root left it beside a hard error,
  every later status, verdict and cleanup read the record as invalid (exit 4)
  and cleanup kept all runtime files. The request's reasons now accept that one
  row reason and nothing else. The S5 test asserts that `status` returns 3
  after the pack hard-error branch; mutant R-S5-VALID reverts the acceptance.
- M2 negative count (low). A decoded view that lost its in-band control
  counted -1 negatives, which the unsigned field cannot carry; the worker failed
  with a sequence gap (`protocol_error`). Each view now counts at least zero
  (`max(0, matches - 1)`).
  `test_m2_negative_count_stays_unsigned_without_inband_control` and mutant
  R-M2-UNSIGNED cover it, and R-19's edit text follows the changed line.

This round's own run was outside any sandbox on the workstation, with a fresh
`TMPDIR` under `/var/tmp`, on `a07b7a24` plus this change. All three repairs
were first reproduced on unmodified `a07b7a24`: the objects-only scan exited 0
as complete, the S5 pack case's `status` returned 4, and the lost in-band M2
control left `protocol_error`. `python3 -I tests/test_canary_proof.py -v` (PATH
`python3` 3.13.15; the fixtures start workers with `/usr/bin/python3` 3.12.3)
ran 143 tests in 1015.455 s, OK, 0 skipped. `python3 -I tests/canary_mutants.py
--check --json` found all 138 mutants applying exactly once and compiling, and
`python3 -I tests/canary_mutants.py --json` (artifacts kept under `--keep`)
reported 138/138 killed after 90/90 passing pristine runs, with the repository
inputs unchanged. The credential, guard and repository suites were not rerun;
none of them imports the changed modules.

Residuals from the re-check that this round does not fix:

- `not_covered` labels a final that completed but is unusable (`final_too_early`
  or `final_stale`) as `requested_incomplete`.
  `test_stream_roots_and_failed_requests_are_described_truthfully` asserts that
  label right after a complete A11 final; no mutant covers the
  requested/not_requested split.
- The `Walk.directory` guard for selected WAL/SHM files without a valid scanned
  main (`sqlite_uri_identity`) has no test of its own: every fixture writes WAL
  magic, so `Scan.file` refuses first, and R-03 removes both checks together.
- `Walk.covered` has no regression test for its exclusion, time-selection,
  special-file-type or symlinked-parent branches; only the tasks-depth branch
  is tested.
- O12: no test asserts the decoded cap in the plan, the shared Git deadline,
  the SQLite family-bytes budget, the new claim fields, the 15-second shutdown
  or the rows' `exits` field.
- G03: the END count/aux check in `Session.outcome` has no mutant; R-04 covers
  only the END status check.
- G13: no mutant deletes `--text` from the scanner argv; D2-49 drops
  `--encoding` and was only relabeled.
- O07: no mutant replaces the set-based physical/logical Git reconcile with a
  count-based one.
- `Session.bind_scope`'s refusal paths and the real `Session.scope_populated`
  parser are untested (`test_scope_stop_failure_cannot_complete` mocks the
  parser); only the native success path ran.
- The scan's own exit code comes from in-memory events that `Run.append` never
  validates (`scan` returns `report(..., exit_only=True)`). This round removes
  the one known disagreement (`inventory_unreconciled`), not the mechanism.
