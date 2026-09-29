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

- On 2026-09-29 the user said "the key can be store with env so no key is
  loss" and "handle the key with seamless sota env practice always" (the
  coordinator's design brief). These state a rule for every key.
- They post-date the 2026-09-26 memory-only placement of Tavily. They also
  post-date the 2026-09-28 "don't store in files" for the keys pasted in chat
  (the Alpaca pairs), which the user already reversed by moving both pairs
  into 0600 files.
- **Reading:** Tavily moves to the 0600 file store, and the keyring keeps at
  most a per-boot spare. The design's root research unit called the two
  instructions conflicting and left the move to the user; this reading
  resolves the conflict by recency and by the user's stated goal that no key
  is lost.
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
  `tests/test_credential_boot_receipt.py` (14 tests: the key allowlist;
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
- The command's process group is ended (`SIGTERM`, 2 s, `SIGKILL`) on every
  way out of the runner. On Linux a killed runner is answered by
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

**Alternatives, with pins and evidence class:**
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
  has started leaves only the parent-death signal. A descendant that leaves
  the process group (`setsid`, `setpgid`) is out of reach of the group kill
  and of the watchdog, and so is a set-user-ID command. Only Linux has been
  run; the watchdog has not been run on macOS. A same-user debugger or
  `ptrace` is out of scope.

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
  `tests/test_credential_run.py` (77 tests) and the schema tests in
  `tests/test_credential_status.py`. The runner tests were written first
  and failed to import the missing tool; the schema tests failed on the
  missing field; each test of a code repair failed before its fix (the
  second round's items 1 and 2 on the previous head). The pinning tests of
  the second round's item 3 passed at once, so a mutant of each rule was
  run against a copy of the previous test module first, and survived it. In
  a scratch mutation run, each of 80 mutants (32 of the first round, 29 for
  the first repair round, 19 for the second, one rule removed or changed
  each time) failed its intended test, and the files were restored by
  sha256. The tests start the runner
  through a test-only launcher on a host whose real `core_pattern` pipes
  crash dumps, which CI runners commonly do; the two tests of the real
  re-execution skip there, and one test checks the real tool against the
  host's own pattern.
- *Upstream source*, read at the pins above on 2026-09-29, and macOS ps(1)
  at apple-oss-distributions/adv_cmds@6bed8737.
- *Measured once in a session scratch directory, no committed receipt*: the
  mise, agentself and dotenvx spikes, the check of this checkout's guard on
  `tvly auth` behind the runner, one run of the 77 runner tests under
  uv-managed CPython 3.9.25 and 3.14.7 on Linux (all pass, with
  `DeprecationWarning` an error in the test process), and one run of
  coreutils `timeout -k` against the runner with a command and a descendant
  that both ignore `SIGTERM`, in a synthetic store: `timeout` killed the
  runner, and both were gone about 3 s after it returned.
- *Not yet observed*: the runner on macOS, including the Command Line Tools
  `python3` and the watchdog, a
  real key through it (the canary harness is a later change), a host that
  pipes crash dumps (the refusal is tested with pattern files, not with a
  real `systemd-coredump` crash), a harness escalation such as `timeout -k`
  (the tests send `SIGKILL` to the runner directly), and the runner's guard
  model and the default-path flip, which are the second phase of this
  change.

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

## Part 5: the canary proof (D1 PR-5, 2026-09-29)

This section amends the record for the change that adds the proof harness
for the key runner. The harness is
[`tools/credentials/canary_e2e.py`](../../tools/credentials/canary_e2e.py),
with its probe, its sink table and a workflow for the workflow-child
consumer. The runbook is
[Proof run (canary)](../secret-storage.md#proof-run-canary).

**Selection.** A synthetic canary is handed to six consumers by inventory
id: a fresh `claude -p` session, its subagent, a workflow child,
`codex exec`, a Codex lane through OmniRoute, and a `systemd-run --user`
unit. The harness then scans the places where a key could be recorded by
mistake.
- Each consumer gets its own canary and nonce, and runs alone: write its
  canary, run it, remove the file. A hit therefore names the consumer's
  path.
- The probe's tag binds the run, the consumer and the nonce, so a stale or
  copied tag fails `verify`.
- The scanned forms are the forms the runner masks (`encoded_forms`), so the
  two lists cannot drift apart.
- Positive controls come first, for each scanner class and for each sink. A
  sink whose planted decoy is missing is "not a sink, or scanned wrongly",
  never clean, and fails the scan.
- The receipt keeps counts, ids, versions, model ids and times, and a test
  holds its key allowlist.

The new inventory row `canary-e2e` has class `test_canary` and status
`test_only`, and `scripts/credential_status.py` accepts the pair only
together.

**Built from.** No upstream harness was found, so the harness follows the
design's research_sinks scan plan and its verification of 2026-09-29 (49
sinks: 37 confirmed, 12 corrected, 13 missed items; design notes, not in
this repository). It reuses code rather than copying it:
- `set_credential.py`'s value grammar, store checks and create-only writer;
- `credential_run.py`'s `encoded_forms` and `child_environment`;
- `credential_status.py`'s schema and store paths;
- `credential_boot_receipt.py`'s `write_receipt` (a dot-file, `os.link`, and
  sequence numbers under a directory lock).

**Alternatives.** Maintained secret scanners, such as kingfisher v2.7.0,
trufflehog v3.97.9 and betterleaks v1.8.1 (versions as the verification
listed them), look for key shapes. They complement a canary scan but
cannot replace it: only a synthetic pattern of known origin gives a zero a
meaning, and only a planted decoy shows that a sink is read at all.

**Deviations from the build contract, with reasons.**
- The subagent and the workflow child fetch their own decoy with
  `canary_e2e.py decoy`, instead of receiving it in the parent's prompt.
  Otherwise the parent's or the coordinator's transcript would satisfy
  their controls in their place.
- Codex reads its prompt from stdin, which the harness closes, instead of
  from argv with stdin on `/dev/null`. This keeps decoys out of argv; the
  known hang comes from a stdin left open.
- Codex `shell_snapshots` and `~/.docker/config.json` join OmniRoute in the
  user-run group, for the design's own reason: they hold real tokens and are
  Read-denied to agents. By the coordinator's decision of the repair round,
  so do the user manager's environment and the container configurations
  (Docker's `config.v2.json` and `hostconfig.json`): an agent-run process
  never reads a real value, even to count.
- Receipts are named by `write_receipt`
  (`<sequence>-<UTC stamp>-<boot id prefix>.json` under
  `<state>/native-agent-stack/canary/`), with the run id inside, not as
  `<run>.json`.
- The Loki dump is matched in memory and never written. The receipt keeps
  whether each tag was valid, not the tags (amendment 11). RTK recall blobs
  are decompressed by their magic bytes, not by the unverified codec column.
- Decoys are printed and put in prompts on purpose, because they are the
  positive controls. "Never prints a pattern" is read as a canary's
  patterns.

**Repair round (2026-09-29).** A read-only GPT-6 review at effort max
returned 14 findings, five of them HIGH false-zero paths. Each was
reproduced with a synthetic fixture that passed the old harness wrongly and
failed first, and each fix has its test:
1. *High.* A client's stderr capture was never scanned. Every capture of
   every consumer, and every tag file, is scanned for every canary, each
   capture with a control line the harness writes into it.
2. *High.* A user-run scan that found a canary still gave `zero`. Every
   executed check now enters the verdict; a kept run needs its after-restart
   check; a user-run scan that did not run is listed in the receipt and
   named in the claim.
3. *High.* Evidence from before a re-run was accepted. Each consumption
   gets a sequence number, a new one moves the older verification, settle
   and scans aside, and `report` accepts only the latest.
4. *High.* An unreadable path or a failed scanner read as clean. Either
   makes the sink INCOMPLETE and fails the scan, and `consume` needs a clean
   and complete baseline.
5. *High.* The members of a multi-member gzip after the first were dropped.
   Every member is decoded, and a limit or an incomplete stream makes the
   value unreadable.
6. *Medium.* Discovered file names reached `rg`'s argv. Only configured
   roots do now, with globs derived from the table, and names are matched
   here.
7. *Medium.* A newline in a file name hid a canary. Paths come from rg's
   JSON output and from the walk's own names.
8. *Medium.* Loki pagination skipped entries that shared a boundary
   timestamp. Boundary entries are kept, and an unfinished dump is
   INCOMPLETE.
9. *Medium.* The RTK control rested on a 40-byte echo that RTK never keeps.
   The Claude run's `rtk err` command now prints about 840 bytes of decoy
   lines, over RTK v0.50.0's 500-byte recall gate
   (`src/core/retriever.rs:18`, `src/core/tee.rs:61-66`), and the recall
   control counts only in the decoded blobs.
10. *Medium.* Only `RLIMIT_CORE` guarded against crash collectors. The
    runner's `check_core_pattern` now runs before any canary exists.
11. *Medium.* A FIFO handed to `rg` blocked the scan. Special files are never
    opened or handed to a scanner, and each sink has a deadline.
12. *Medium.* An interruption left the client running and the store armed.
    SIGTERM and SIGHUP are handled, and the runner's `end_group` and
    watchdog end the client. An interrupted consume leaves a record that
    `report` refuses.
13. *Medium.* Cleanup of one run removed another run's armed file. The
    arming run is recorded under a lock of the store directory, and the
    other runs' steps refuse.
14. *Medium.* The scrub assertion passed without the scrub. The fixture now
    carries a sentinel under every inventory, `must_not_be_set` and pointer
    name, and every environment the harness builds is checked for them.

**Evidence class.**
- *Local integration*, with synthetic values in temporary directories:
  `tests/test_canary_e2e.py`, and the status tests in
  `tests/test_credential_status.py`. The tests were written first and failed
  to import the harness; the status tests failed on the unknown status and
  class; the docs tests failed until the runbook section existed. One test
  runs all six consumers through stub clients that execute the real runner
  and probe against a temporary store, and ends in a receipt with
  `result: zero`.
- *Scratch mutation runs*, not committed. For the build, each of 14 mutants
  removed one rule and failed its test. For the repair round there were 42
  mutants, the earlier rules and one per new rule; 41 failed their tests.
  The survivor is the Loki one-timestamp early exit on its own: the rule
  that a page adding nothing new is INCOMPLETE stops the same fixture one
  page later. The files were restored and checked by sha256 each time.
- *Not yet observed*: the live window with real clients. Until then there is
  no receipt, the sink table's rows remain unverified sink facts, and the
  client flags in the harness (`claude -p --output-format stream-json`,
  `codex exec --json -s read-only`) come from native `--help` output on this
  host, not from a run.

**Known limits.** The proof covers the cooperative, id-only path.
- It says nothing about adversarial or careless agents, transformed forms,
  process memory and swap, remote retention, Windows-side stores or future
  client versions.
- Until the command guard lists `CANARY_E2E_KEY` in `SECRET_NAMES`, the
  guard does not treat the canary's variable name as it treats a real
  key's name.
- Any unreadable path makes its sink INCOMPLETE. A `/tmp` that holds other
  users' unreadable files, a `gh` without network or sign-in, or a zstd
  value on a Python without a zstd decoder therefore fails the pass until
  the sink table's exclusions are triaged or the tool is available. The
  table excludes only root's PrivateTmp and snap directories by name.

**Overturn.**
- A sink whose control fails in the live window: correct its row, then
  rerun.
- A canary found anywhere: stop, record the path, and fix it before any
  real key takes that path.
- A maintained tool that runs positive-controlled canary scans over these
  sinks with value-free output: compare it head to head.
